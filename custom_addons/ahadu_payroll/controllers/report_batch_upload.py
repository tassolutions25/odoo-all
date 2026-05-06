# -*- coding: utf-8 -*-
import io
import logging
import zipfile
import urllib.parse
from collections import defaultdict
from odoo import http, fields
from odoo.http import request
from odoo.tools.misc import xlsxwriter
from odoo.exceptions import UserError
from .common import AhaduReportCommon

_logger = logging.getLogger(__name__)

class BatchUploadReport(AhaduReportCommon):

    def _get_finance_gl(self, rule_code, emp_type_code, side='D', gl_from_rule=None):
        """
        GL mapping based on Finance requirements.
        """
        if side == 'D':
            # Earnings / Expenses (DEBIT)
            if rule_code == 'BASIC':
                return '5030101' if emp_type_code == 'CL_STAFF' else '5030102'
            if rule_code == 'OT':
                return '5030104' if emp_type_code == 'CL_STAFF' else '5030105'
            if rule_code == 'ACTING': return '5030103'
            if rule_code == 'TRANS': return '5030204'
            if rule_code == 'HARDSHIP': return '5030203'
            if rule_code == 'HOUSE': return '5030205'
            if rule_code == 'REP': return '5030206'
            if rule_code == 'PENSION_COMP': return '5030211'
            if rule_code == 'SHIFT': return '5030215'
            if rule_code == 'OTHER_BEN': return '5030220'
            if rule_code == 'CASH_IND': return '5030201'
            if rule_code == 'MOBILE': return '5030221'
            return gl_from_rule or 'N/A'
        else:
            # Deductions / Payables (CREDIT)
            if rule_code in ['TAX', 'CI_TAX']: return '2020301'
            if rule_code in ['PENSION_EMP', 'PENSION_COMP']: return '2020308'
            if rule_code == 'COST_SHARING': return '2020309'
            if rule_code == 'PENALTY': return '4050012'
            if rule_code == 'LOAN': return '1010202'
            if rule_code == 'LOAN_PERS': return '1010203'
            return gl_from_rule or 'N/A'

    @http.route('/ahadu_payroll/batch_upload/<int:batch_id>', type='http', auth='user')
    def download_batch_upload(self, batch_id, **kw):
        batch = request.env['hr.payslip.run'].browse(batch_id)
        if not batch.exists() or batch.state != 'close':
            raise UserError("You cannot generate the Batch Upload files until the payroll batch is Approved and Closed.")

        # Data structures for the 3 files
        file1_data = [] # PL misre finance (Aggregated Deductions)
        file2_data = [] # Cost Center Bulk upload (Breakdown Earnings)
        file3_data = [] # Salary Bulk Upload (Individual Transfers)

        slips = self._get_payslip_lines(batch)
        month_year = batch.date_start.strftime('%b %Y') if batch.date_start else ''
        
        # Aggregation buckets
        file1_aggregated = defaultdict(float) # {(account, dc, reason): amount}
        file2_aggregated = defaultdict(float) # {(gl_prefix, dc, dept_cc, reason, branch_cc): amount}
        
        total_net_all = 0.0
        
        # Funding/Clearing Account
        HO_CLEARING = '1040309'

        for slip in slips:
            emp = slip.employee_id
            emp_type = emp.ahadu_employee_type_id.code or 'N/A'
            emp_type_name = 'clerical staff' if emp_type == 'CL_STAFF' else 'non clerical staff'
            branch = emp.branch_id
            branch_code = branch.cost_center_id.code or '0000'
            is_ho = branch.name == 'Head Office' or branch_code == '9999'
            
            branch_prefix = '9999' if is_ho else branch_code
            dept_cc = slip.contract_id.cost_center_id.code or branch_prefix
            # Ensure dept_cc is properly formatted (e.g., 999917)
            if is_ho and dept_cc and '-' in dept_cc:
                dept_cc = dept_cc.replace('-', '')
            
            # File 2: Earnings Breakdown
            for line in slip.line_ids:
                code = line.code
                amount = line.total
                if amount == 0: continue

                # Earnings (Debit side for File 2)
                if code in ['BASIC', 'OT', 'ACTING', 'TRANS', 'HARDSHIP', 'HOUSE', 'REP', 'PENSION_COMP', 'SHIFT', 'OTHER_BEN', 'MOBILE']:
                    gl = self._get_finance_gl(code, emp_type, side='D')
                    reason = f"{emp_type_name} {line.name.lower()} {month_year}"
                    file2_aggregated[(f"{branch_prefix}-{gl}", 'D', dept_cc, reason, branch_prefix)] += amount

                # Deductions (Credit side for File 1 aggregation)
                if code in ['TAX', 'PENSION_EMP', 'PENSION_COMP', 'COST_SHARING']:
                    gl = self._get_finance_gl(code, emp_type, side='C')
                    reason = f"{line.name.lower()} {'HO staff' if is_ho else 'branch staff'} {month_year}"
                    file1_aggregated[(f"{branch_prefix}-{gl}", 'C', reason)] += amount
                
                elif code == 'PENALTY':
                    gl = self._get_finance_gl(code, emp_type, side='C')
                    reason = f"penalty deduction {month_year}"
                    file1_aggregated[(f"{branch_prefix}-{gl}", 'C', reason)] += abs(amount)

            # Special case for Cash Indemnity (often a separate component)
            if slip.cash_indemnity_allowance > 0:
                gl = '5030201'
                reason = f"{emp_type_name} cash indemnity allowance {month_year}"
                file2_aggregated[(f"{branch_prefix}-{gl}", 'D', dept_cc, reason, branch_prefix)] += slip.cash_indemnity_allowance

            # File 3: Individual Transfers
            # 1. Net Salary
            net = self._get_rule_total(slip, 'NET')
            # Adjust for CI portion if distributed separately
            if slip.net_cash_indemnity > 0:
                net = round(net - slip.net_cash_indemnity, 2)
            
            if net > 0:
                acc = self._get_bank_account(emp, 'salary') or 'N/A'
                file3_data.append((acc, 'C', net))
                total_net_all += net
            
            # 2. Loans (Mandatory individual disbursement accounts)
            loans = request.env['hr.loan'].sudo().search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'approved'),
                ('date_start', '<=', batch.date_end),
            ])
            
            adv_actual = sum(slip.line_ids.filtered(lambda l: l.code == 'ADV_LOAN').mapped('total'))
            pers_actual = sum(slip.line_ids.filtered(lambda l: l.code == 'PERS_LOAN').mapped('total'))
            other_actual = sum(slip.line_ids.filtered(lambda l: l.code == 'OTHER_LOAN').mapped('total'))
            
            active_loans = []
            for loan in loans:
                # Active check
                is_active = False
                if getattr(loan, 'is_external', False):
                    if loan.remaining_amount > 0:
                        is_active = True
                elif loan.paid_installments < loan.installment_months:
                    if batch.date_end >= loan.date_start:
                        is_active = True
                        
                if is_active:
                    active_loans.append(loan)

            adv_types = ['Emergency/Salary Advance Loan']
            pers_types = ['Personal Staff Loan']
            
            adv_target_total = sum(l.monthly_installment for l in active_loans if l.loan_type_id.name in adv_types)
            pers_target_total = sum(l.monthly_installment for l in active_loans if l.loan_type_id.name in pers_types)
            other_target_total = sum(l.monthly_installment for l in active_loans if l.loan_type_id.name not in adv_types and l.loan_type_id.name not in pers_types)
            
            for loan in active_loans:
                target = loan.monthly_installment
                if target <= 0:
                    continue
                
                ltype = loan.loan_type_id.name
                if ltype in adv_types:
                    amt = round((target / adv_target_total) * adv_actual, 2) if adv_target_total else 0.0
                elif ltype in pers_types:
                    amt = round((target / pers_target_total) * pers_actual, 2) if pers_target_total else 0.0
                else:
                    amt = round((target / other_target_total) * other_actual, 2) if other_target_total else 0.0
                
                if amt > 0:
                    # Use the specific bank account linked to THIS loan
                    acc = loan.bank_account_id.account_number or self._get_bank_account(emp, loan.loan_type_id.bank_account_type or 'loan_settlement') or 'N/A'
                    file3_data.append((acc, 'C', amt))
                    total_net_all += amt

            # 3. Cash Indemnity Distribution
            if slip.cash_indemnity_allowance > 0:
                if slip.ci_to_balance > 0:
                    acc = self._get_bank_account(emp, 'cash_indemnity') or 'N/A'
                    file3_data.append((acc, 'C', slip.ci_to_balance))
                    total_net_all += slip.ci_to_balance
                if slip.ci_to_salary > 0:
                    acc = self._get_bank_account(emp, 'salary') or 'N/A'
                    file3_data.append((acc, 'C', slip.ci_to_salary))
                    total_net_all += slip.ci_to_salary

        # Finalizing File 1 (Adding Debit lines for each credited total)
        for (gl_full, dc, reason), amount in file1_aggregated.items():
            # Add the Credit line
            file1_data.append((gl_full, 'C', amount, reason))
            # Add the matching Debit line from Clearing
            prefix = gl_full.split('-')[0]
            file1_data.append((f"{prefix}-{HO_CLEARING}", 'D', amount, reason))

        # Finalizing File 3 (Adding Total Debit line)
        # Note: The example showed 9999-1040309 as debit. We use HO_CLEARING.
        if total_net_all > 0:
            file3_data.insert(0, (f"9999-{HO_CLEARING}", 'D', round(total_net_all, 2)))

        # --- Generate ZIP with 3 Excels ---
        zip_buffer = io.BytesIO()
        try:
            with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                def create_workbook():
                    out = io.BytesIO()
                    wb = xlsxwriter.Workbook(out, {'in_memory': True})
                    st_text = wb.add_format({'font_name': 'Arial', 'font_size': 10})
                    st_money = wb.add_format({'font_name': 'Arial', 'font_size': 10, 'num_format': '#,##0.00'})
                    return out, wb, st_text, st_money

                safe_batch_name = (batch.name or 'Batch').replace('/', '_').replace('\\', '_')

                # FILE 1: PL misre finance
                out1, wb1, st1, mon1 = create_workbook()
                ws1 = wb1.add_worksheet('PL misre finance')
                for r, row_data in enumerate(file1_data):
                    ws1.write(r, 0, row_data[0], st1)
                    ws1.write(r, 1, row_data[1], st1)
                    ws1.write(r, 2, row_data[2], mon1)
                    ws1.write(r, 3, row_data[3], st1)
                wb1.close()
                zip_file.writestr(f"Bulk Upload PL misre finance {safe_batch_name}.xlsx", out1.getvalue())

                # FILE 2: Cost Center Bulk upload
                out2, wb2, st2, mon2 = create_workbook()
                ws2 = wb2.add_worksheet('Cost Center Bulk upload')
                # Sorted File 2 data
                sorted_f2_keys = sorted(file2_aggregated.keys())
                for r, key in enumerate(sorted_f2_keys):
                    amt = file2_aggregated[key]
                    ws2.write(r, 0, key[0], st2) # 9999-GL
                    ws2.write(r, 1, key[1], st2) # D
                    ws2.write(r, 2, amt, mon2)    # Amount
                    ws2.write(r, 3, key[2], st2) # Dept CC
                    ws2.write(r, 4, key[3], st2) # Reason
                    ws2.write(r, 5, key[4], st2) # HO Prefix / Branch Prefix
                wb2.close()
                zip_file.writestr(f"{safe_batch_name} Cost Center Bulk upload.xlsx", out2.getvalue())

                # FILE 3: Salary Bulk Upload
                out3, wb3, st3, mon3 = create_workbook()
                ws3 = wb3.add_worksheet('Salary Bulk Upload')
                for r, row_data in enumerate(file3_data):
                    ws3.write(r, 0, row_data[0], st3)
                    ws3.write(r, 1, row_data[1], st3)
                    ws3.write(r, 2, row_data[2], mon3)
                wb3.close()
                zip_file.writestr(f"Third Salary Bulk Upload {safe_batch_name}.xlsx", out3.getvalue())

        except Exception as e:
            _logger.error(f"CBS Batch Upload Generation Failed: {str(e)}")
            raise UserError(f"Generation failed: {str(e)}")

        zip_buffer.seek(0)
        zip_filename = f"CBS_Batch_Upload_{safe_batch_name}.zip"
        quoted_filename = urllib.parse.quote(zip_filename)
        headers = [
            ('Content-Type', 'application/zip'),
            ('Content-Disposition', f'attachment; filename*=UTF-8\'\'{quoted_filename}'),
            ('Cache-Control', 'no-cache, no-store, must-revalidate'),
        ]
        return request.make_response(zip_buffer.getvalue(), headers=headers)
