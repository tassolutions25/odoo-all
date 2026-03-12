# -*- coding: utf-8 -*-
import io
import requests
import json
import logging
import zipfile
import uuid
import urllib.parse
from collections import defaultdict
from odoo import http, fields
from odoo.http import request
from odoo.tools.misc import xlsxwriter
from odoo.exceptions import UserError
from .common import AhaduReportCommon

_logger = logging.getLogger(__name__)

class BankTransferReport(AhaduReportCommon):
    
    def _is_addis_branch(self, branch):
        """Helper to check if a branch is in Addis Ababa."""
        if not branch or not branch.region_id:
            return False
        return 'addis' in (branch.region_id.name or '').lower()

    def _get_finance_gl(self, rule_code, emp_type_code, side='D', gl_from_rule=None):
        """
        Custom GL mapping for earnings and deductions based on Finance requirements list.
        side: 'D' for Debit (Expense), 'C' for Credit (Payable/Deduction)
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
            if rule_code in ['PENSION_EMP', 'PENSION_COMP']: return '2020308' # Both contribute to total 18%
            if rule_code == 'COST_SHARING': return '2020309'
            if rule_code == 'PENALTY': return '4050012'
            if rule_code == 'LOAN': return '1010202'
            if rule_code == 'LOAN_PERS': return '1010203'
            return gl_from_rule or 'N/A'

    @http.route('/ahadu_payroll/bank_transfer/<int:batch_id>', type='http', auth='user')
    def download_bank_transfer(self, batch_id, **kw):
        batch = request.env['hr.payslip.run'].browse(batch_id)
        
        if not batch.exists() or batch.state != 'close':
            raise UserError("You cannot generate the Bank Transfer File until the payroll batch is Approved and Closed.")

        if batch.bank_transfer_done:
            raise UserError("The Bank Transfer has already been processed for this batch. You cannot pay twice.")

        # Aggregate Upload Data: {(account, dc, dept_cc, reason, branch_cc): amount}
        aggregated_upload = defaultdict(float)
        # file3_payments: {(account, funding_gl): {'amount': sum, 'emp': []}}
        file3_payments = defaultdict(lambda: {'amount': 0.0, 'emp': []})
        
        slips = self._get_payslip_lines(batch)
        month_year = batch.date_start.strftime('%b %Y') if batch.date_start else ''
        
        STATUTORY_RULES = ['TAX', 'CI_TAX', 'PENSION_EMP', 'PENSION_COMP', 'COST_SHARING']
        INDIVIDUAL_TRANSFER_RULES = ['NET', 'LOAN', 'SAVINGS', 'CREDIT_ASSOC', 'OTHER_DED', 'CASH_IND', 'ADV_LOAN', 'PERS_LOAN', 'OTHER_LOAN']

        for slip in slips:
            emp = slip.employee_id
            emp_type = emp.ahadu_employee_type_id.code or 'N/A'
            emp_type_name = 'clerical staff' if emp_type == 'CL_STAFF' else 'non clerical staff'
            branch = emp.branch_id
            branch_code = branch.cost_center_id.code or '0000'
            is_ho = branch.name == 'Head Office' or branch_code == '9999'
            is_addis = self._is_addis_branch(branch)
            
            branch_prefix = '9999' if is_ho else branch_code
            dept_cc = slip.contract_id.cost_center_id.code or branch_prefix
            branch_cc = branch_prefix

            # Dynamic Funding GLs for API
            FUNDING_GL_SALARY = '5030101' if emp_type == 'CL_STAFF' else '5030102'
            FUNDING_GL_CI = '5030201'

            for line in slip.line_ids:
                rule = line.salary_rule_id
                code = rule.code
                amount = line.total
                if amount == 0: continue

                # DEBIT SIDE (Earnings / Employer Pension)
                if code == 'CASH_IND':
                    # Skip here, we handle CI explicitly below using computed fields
                    continue

                if code in ['BASIC', 'OT', 'ACTING', 'TRANS', 'HARDSHIP', 'HOUSE', 'REP', 'PENSION_COMP', 'SHIFT', 'OTHER_BEN', 'MOBILE'] or rule.ahadu_debit_account_id:
                    gl = self._get_finance_gl(code, emp_type, side='D', gl_from_rule=rule.ahadu_debit_account_id.code if rule.ahadu_debit_account_id else None)
                    reason = f"{emp_type_name} {(rule.name or code).lower()} {month_year}"
                    aggregated_upload[(f"{branch_prefix}-{gl}", 'D', dept_cc, reason, branch_cc)] += amount

                # CREDIT SIDE (Statutory & General Deductions)
                # Skip NET as it's handled explicitly for bank account routing
                if code == 'NET': continue

                if code in STATUTORY_RULES:
                    gl = self._get_finance_gl(code, emp_type, side='C')
                    crediting_branch = branch_prefix
                    if not is_ho and is_addis:
                        crediting_branch = '9999'
                    
                    reason_map = {
                        'TAX': 'income tax',
                        'CI_TAX': 'income tax (ci)',
                        'PENSION_EMP': 'pension pay staff 18 per',
                        'PENSION_COMP': 'pension pay staff 18 per',
                        'COST_SHARING': 'cost sharing'
                    }
                    reason = f"{reason_map.get(code, (rule.name or code).lower())} {'ho staffs' if crediting_branch == '9999' else ''} {month_year}"
                    aggregated_upload[(f"{crediting_branch}-{gl}", 'C', '', reason, branch_cc if crediting_branch != '9999' else '')] += amount
                
                elif code == 'PENALTY':
                    gl = self._get_finance_gl(code, emp_type, side='C')
                    reason = f"penalty deduction {month_year}"
                    aggregated_upload[(f"{branch_prefix}-{gl}", 'C', '', reason, branch_cc)] += abs(amount)
                
                elif rule.ahadu_credit_account_id and code not in INDIVIDUAL_TRANSFER_RULES:
                    gl = self._get_finance_gl(code, emp_type, side='C', gl_from_rule=rule.ahadu_credit_account_id.code)
                    reason = f"{(rule.name or code).lower()} {month_year}"
                    aggregated_upload[(f"{branch_prefix}-{gl}", 'C', '', reason, branch_cc)] += amount

            # --- Explicit Adjustments (Once Per Slip) ---
            
            # 1. Cash Indemnity Debit
            if slip.cash_indemnity_allowance > 0:
                gl = '5030201' # CI Allowance GL
                reason = f"{emp_type_name} cash indemnity allowance {month_year}"
                aggregated_upload[(f"{branch_prefix}-{gl}", 'D', dept_cc, reason, branch_cc)] += round(slip.cash_indemnity_allowance, 2)

            # 2. Individual Transfers (Bank Accounts)
            # Net Salary
            net = self._get_rule_total(slip, 'NET')
            # Subtract the portion going to CI accounts to avoid double-crediting
            if slip.net_cash_indemnity > 0:
                net = round(net - slip.net_cash_indemnity, 2)

            if net > 0:
                acc = self._get_bank_account(emp, 'salary') or 'N/A'
                funding_gl = self._get_finance_gl('BASIC', emp_type, side='D')
                file3_payments[(acc, funding_gl)]['amount'] += net
                if emp.name not in file3_payments[(acc, funding_gl)]['emp']:
                    file3_payments[(acc, funding_gl)]['emp'].append(emp.name)
                aggregated_upload[(acc, 'C', '', f'net salary payment {month_year}', branch_cc)] += net

            # Loans & Advances (New HR Loan Model)
            loans = request.env['hr.loan'].sudo().search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'approved'),
                ('date_start', '<=', batch.date_end),
            ])
            for loan in loans:
                # Same check as in hr_payslip.py to ensure it's still active
                if loan.paid_installments < loan.installment_months and batch.date_end >= loan.date_start:
                    amt = round(loan.monthly_installment, 2)
                    if amt > 0:
                        ltype = loan.loan_type_id
                        acc_type = ltype.bank_account_type or 'loan_settlement'
                        
                        # Funding GL mapping
                        # Default to 1010202, use 1010203 for Personal loans
                        funding_gl = '1010203' if 'personal' in (ltype.name or '').lower() else '1010202'

                        # Priority 1: Use specific disbursement account from the loan
                        # Priority 2: Use mapping based on loan type
                        acc = loan.bank_account_id.account_number or self._get_bank_account(emp, acc_type) or 'N/A'
                        
                        file3_payments[(acc, funding_gl)]['amount'] += amt
                        desc = f"{(ltype.name or 'loan').lower()} {month_year}"
                        aggregated_upload[(acc, 'C', '', desc, branch_cc)] += amt

            # Cash Indemnity Distribution
            if slip.cash_indemnity_allowance > 0:
                if slip.ci_to_balance > 0:
                    acc = self._get_bank_account(emp, 'cash_indemnity') or 'N/A'
                    file3_payments[(acc, FUNDING_GL_CI)]['amount'] += slip.ci_to_balance
                    aggregated_upload[(acc, 'C', '', f'ci block deposit {month_year}', branch_cc)] += slip.ci_to_balance
                if slip.ci_to_salary > 0:
                    acc = self._get_bank_account(emp, 'salary') or 'N/A'
                    file3_payments[(acc, FUNDING_GL_CI)]['amount'] += slip.ci_to_salary
                    aggregated_upload[(acc, 'C', '', f'ci salary credit {month_year}', branch_cc)] += slip.ci_to_salary

            # Other Specific Deductions (Savings, Credit Assoc, etc.)
            # These are usually sent to specific internal/external accounts
            for rule_code, acc_type, funding_gl in [
                ('SAVINGS', 'savings', '2020310'),
                ('CREDIT_ASSOC', 'credit_association', '2020311'),
                ('OTHER_DED', 'other_deduction', '2020312')
            ]:
                amt = self._get_rule_total(slip, rule_code)
                if amt > 0:
                    acc = self._get_bank_account(emp, acc_type) or 'N/A'
                    file3_payments[(acc, funding_gl)]['amount'] += amt
                    desc = f"{(rule_code.replace('_', ' ')).lower()} payment {month_year}"
                    aggregated_upload[(acc, 'C', '', desc, branch_cc)] += amt

        # --- Generate Excels ---
        zip_buffer = io.BytesIO()
        try:
            with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                def get_workbook():
                    out = io.BytesIO()
                    wb = xlsxwriter.Workbook(out, {'in_memory': True})
                    st_text = wb.add_format({'font_name': 'Times New Roman', 'font_size': 11})
                    st_money = wb.add_format({'font_name': 'Times New Roman', 'font_size': 11, 'num_format': '#,##0.00'})
                    return out, wb, st_text, st_money

                safe_batch_name = (batch.name or 'Batch').replace('/', '_').replace('\\', '_').replace(':', '_')

                # FILE 1: Finance Upload
                f_out, f_wb, f_st, f_curr = get_workbook()
                f_ws = f_wb.add_worksheet('Finance Upload')
                row = 0
                # Sort: 'D' before 'C', then by Account
                sorted_keys = sorted(aggregated_upload.keys(), key=lambda x: (x[1] == 'C', x[0]))
                for key in sorted_keys:
                    amt = aggregated_upload[key]
                    f_ws.write(row, 0, key[0], f_st)
                    f_ws.write(row, 1, key[1], f_st)
                    f_ws.write(row, 2, amt, f_curr)
                    f_ws.write(row, 3, key[2], f_st)
                    f_ws.write(row, 4, key[3], f_st)
                    f_ws.write(row, 5, key[4], f_st)
                    row += 1
                f_wb.close()
                zip_file.writestr(f"1_Finance_Upload_{safe_batch_name}.xlsx", f_out.getvalue())

                # FILE 2: Bank Transfer Details
                f3_out, f3_wb, f3_st, f3_curr = get_workbook()
                f3_ws = f3_wb.add_worksheet('Bank Transfer Details')
                row = 0
                for (acc, funding_gl), data in file3_payments.items():
                    raw_id = f"{batch.name}-{acc}-{funding_gl}"
                    request_id = f"PAY-{uuid.uuid3(uuid.NAMESPACE_DNS, raw_id).hex[:10].upper()}"
                    status = self._call_payroll_api(request_id, data['amount'], acc, funding_gl)
                    
                    f3_ws.write(row, 0, acc, f3_st)
                    f3_ws.write(row, 1, 'C', f3_st)
                    f3_ws.write(row, 2, data['amount'], f3_curr)
                    desc = f"{', '.join(data['emp'][:3])}{'...' if len(data['emp']) > 3 else ''} {batch.name}"
                    f3_ws.write(row, 3, desc, f3_st)
                    f3_ws.write(row, 4, status, f3_st)
                    row += 1
                f3_wb.close()
                zip_file.writestr(f"2_Bank_Transfer_Details_{safe_batch_name}.xlsx", f3_out.getvalue())

            batch.sudo().write({'bank_transfer_done': True})
            
        except Exception as e:
            _logger.error(f"Bank Transfer Generation Failed: {str(e)}")
            raise UserError(f"Generation failed: {str(e)}")

        zip_buffer.seek(0)
        zip_filename = f"Bank_Transfer_Finance_{safe_batch_name}.zip"
        quoted_filename = urllib.parse.quote(zip_filename)
        headers = [
            ('Content-Type', 'application/zip'),
            ('Content-Disposition', f'attachment; filename*=UTF-8\'\'{quoted_filename}'),
            ('Cache-Control', 'no-cache, no-store, must-revalidate'),
        ]
        return request.make_response(zip_buffer.getvalue(), headers=headers)
