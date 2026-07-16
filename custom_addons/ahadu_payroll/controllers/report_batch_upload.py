# -*- coding: utf-8 -*-
import io
import logging
import zipfile
import urllib.parse
from collections import defaultdict
import xlwt
from odoo import http, fields
from odoo.http import request
from odoo.exceptions import UserError
from .common import AhaduReportCommon

_logger = logging.getLogger(__name__)

class BatchUploadReport(AhaduReportCommon):

    def _create_xls_workbook(self):
        out = io.BytesIO()
        wb = xlwt.Workbook(encoding='utf-8')
        st_text = xlwt.easyxf('font: name Arial, height 200;')
        st_money = xlwt.easyxf('font: name Arial, height 200;', num_format_str='#,##0.00')
        return out, wb, st_text, st_money

    def _create_cost_center_workbook(self):
        out = io.BytesIO()
        wb = xlwt.Workbook(encoding='utf-8')
        style = xlwt.easyxf('font: name Calibri, height 220;')
        return out, wb, style

    def _prepare_cost_center_sheet(self, workbook):
        worksheet = workbook.add_sheet('Sheet1')
        worksheet.col(0).width = 3181
        worksheet.col(2).width = 2779
        worksheet.col(4).width = 8301
        return worksheet

    def _save_xls_workbook(self, workbook, output):
        workbook.save(output)
        output.seek(0)
        return output.getvalue()

    def _truncate_description(self, description, max_length=30):
        return (str(description or ''))[:max_length]

    def _format_cost_center_code(self, code):
        if not code:
            return ''
        code = str(code).replace('-', '')
        return code.zfill(4) if len(code) < 4 else code

    def _format_branch_cost_center_value(self, code):
        return self._format_cost_center_code(code)

    def _validate_balanced_entries(self, entries, file_label):
        debit_total = round(sum(amount for _, dc, amount, *_ in entries if dc == 'D'), 2)
        credit_total = round(sum(amount for _, dc, amount, *_ in entries if dc == 'C'), 2)
        if debit_total != credit_total:
            raise UserError(
                "%s is not balanced. Debit total: %.2f, Credit total: %.2f."
                % (file_label, debit_total, credit_total)
            )

    def _add_clearing_credit(self, aggregated, branch_prefix, clearing_gl, amount, reason):
        amount = round(abs(amount or 0.0), 2)
        if amount:
            aggregated[(f"{branch_prefix}-{clearing_gl}", 'C', '', reason, '')] += amount

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
        file1_aggregated = defaultdict(float) # {(d_prefix, c_prefix, gl, dc, reason): amount}
        file2_aggregated = defaultdict(float) # {(gl_prefix, dc, dept_cc, reason, branch_cc): amount}
        
        total_net_per_branch = defaultdict(float)
        
        # Funding/Clearing Account
        HO_CLEARING = '1040309'
        statutory_rules = ['TAX', 'CI_TAX', 'PENSION_EMP', 'PENSION_COMP', 'COST_SHARING']
        clearing_deduction_rules = [
            'ADV_LOAN', 'PERS_LOAN', 'OTHER_LOAN', 'LOAN',
            'SAVINGS', 'CREDIT_ASSOC', 'OTHER_DED', 'LOP_LEAVE',
        ]

        for slip in slips:
            emp = slip.employee_id
            emp_type = emp.ahadu_employee_type_id.code or 'N/A'
            emp_type_name = 'clerical staff' if emp_type == 'CL_STAFF' else 'non clerical staff'
            branch = emp.branch_id
            branch_code = branch.cost_center_id.code or '0000'
            is_ho = branch.name == 'Head Office' or branch_code == '9999'
            is_addis = bool((branch.region_id and branch.region_id.name and branch.region_id.name.lower() == 'addis ababa') or \
                            (emp.region_id and emp.region_id.name and emp.region_id.name.lower() == 'addis ababa'))
            
            branch_prefix = '9999' if is_ho else str(branch_code)
            c_prefix = '9999' if (is_ho or is_addis) else branch_prefix
            
            dept_cc = str(slip.contract_id.cost_center_id.code or branch_prefix)
            # Ensure dept_cc is properly formatted (e.g., 999917)
            if is_ho and '-' in dept_cc:
                dept_cc = dept_cc.replace('-', '')
            dept_cc = self._format_cost_center_code(dept_cc)
            
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
                if code in statutory_rules:
                    gl = self._get_finance_gl(code, emp_type, side='C')
                    
                    if code in ['PENSION_EMP', 'PENSION_COMP']:
                        reason_f1 = f"PENSION 18PER {'HO staff' if is_ho else 'branch staff'} {month_year}"
                        reason_f2 = f"PENSION 18PER for {month_year}"
                    elif code in ['TAX', 'CI_TAX']:
                        reason_f1 = f"EIT {'HO staff' if is_ho else 'branch staff'} {month_year}"
                        reason_f2 = f"EIT for {month_year}"
                    else:
                        reason_f1 = f"{line.name.lower()} {'HO staff' if is_ho else 'branch staff'} {month_year}"
                        reason_f2 = f"{line.name.lower()} {month_year}"
                        
                    file1_aggregated[(branch_prefix, c_prefix, gl, 'C', reason_f1)] += abs(amount)
                    self._add_clearing_credit(file2_aggregated, branch_prefix, HO_CLEARING, amount, reason_f2)
                
                elif code == 'PENALTY':
                    gl = self._get_finance_gl(code, emp_type, side='C')
                    reason = f"penalty deduction {month_year}"
                    file1_aggregated[(branch_prefix, c_prefix, gl, 'C', reason)] += abs(amount)
                    self._add_clearing_credit(file2_aggregated, branch_prefix, HO_CLEARING, amount, reason)
                    
                elif code == 'CAMPAIGN':
                    # Split campaign amounts proportionally among active campaigns
                    campaign_deductions = slip.employee_id.deduction_ids.filtered(lambda d: 
                        d.deduction_type == 'campaign' and d.state == 'active' and 
                        (not d.start_date or d.start_date <= slip.date_to) and
                        (not d.end_date or d.end_date >= slip.date_from)
                    )
                    total_campaign_target = sum(d.monthly_amount for d in campaign_deductions)
                    if total_campaign_target > 0:
                        for d in campaign_deductions:
                            camp_amt = round((d.monthly_amount / total_campaign_target) * abs(amount), 2)
                            if camp_amt > 0 and d.campaign_id and d.campaign_id.credit_account_id:
                                camp_gl = d.campaign_id.credit_account_id.code
                                reason = f"campaign {d.campaign_id.name.lower()} {month_year}"
                                file1_aggregated[(branch_prefix, c_prefix, camp_gl, 'C', reason)] += camp_amt
                                self._add_clearing_credit(file2_aggregated, branch_prefix, HO_CLEARING, camp_amt, reason)
                                
                elif code in clearing_deduction_rules:
                    reason = f"{line.name.lower()} {month_year}"
                    self._add_clearing_credit(file2_aggregated, branch_prefix, HO_CLEARING, amount, reason)

            # Special case for Cash Indemnity (often a separate component)
            if slip.cash_indemnity_allowance > 0:
                gl = '5030201'
                reason = f"{emp_type_name} cash indemnity allowance {month_year}"
                file2_aggregated[(f"{branch_prefix}-{gl}", 'D', dept_cc, reason, branch_prefix)] += slip.cash_indemnity_allowance

            # File 3: Individual Transfers
            # 1. Net Salary
            net = self._get_rule_total(slip, 'NET')
            # NET already excludes the CI balance allocation through the ALC
            # category, so only remove the CI amount separately paid to salary.
            if slip.ci_to_salary > 0:
                net = round(net - slip.ci_to_salary, 2)
            
            if net > 0:
                acc = self._get_bank_account(emp, 'salary') or 'N/A'
                file3_data.append((acc, 'C', net))
                total_net_per_branch[branch_prefix] += net
                
                reason_f2 = f"NET SALARY {month_year}"
                self._add_clearing_credit(file2_aggregated, branch_prefix, HO_CLEARING, net, reason_f2)
            
            # 2. Loans (Mandatory individual disbursement accounts)
            loans = request.env['hr.loan'].sudo().search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'approved'),
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
                    total_net_per_branch[branch_prefix] += amt

            # 3. Cash Indemnity Distribution
            if slip.cash_indemnity_allowance > 0:
                if slip.ci_to_balance > 0:
                    acc = self._get_bank_account(emp, 'cash_indemnity') or 'N/A'
                    file3_data.append((acc, 'C', slip.ci_to_balance))
                    total_net_per_branch[branch_prefix] += slip.ci_to_balance
                    
                    reason_f2 = f"cash indemnity balance {month_year}"
                    self._add_clearing_credit(file2_aggregated, branch_prefix, HO_CLEARING, slip.ci_to_balance, reason_f2)
                    
                if slip.ci_to_salary > 0:
                    acc = self._get_bank_account(emp, 'salary') or 'N/A'
                    file3_data.append((acc, 'C', slip.ci_to_salary))
                    total_net_per_branch[branch_prefix] += slip.ci_to_salary
                    
                    reason_f2 = f"cash indemnity to salary {month_year}"
                    self._add_clearing_credit(file2_aggregated, branch_prefix, HO_CLEARING, slip.ci_to_salary, reason_f2)

        # Finalizing File 1 (Adding Debit lines for each credited total)
        for (d_prefix, c_prefix, gl, dc, reason), amount in file1_aggregated.items():
            # Add the Credit line
            file1_data.append((f"{c_prefix}-{gl}", 'C', amount, reason))
            # Add the matching Debit line from Clearing
            file1_data.append((f"{d_prefix}-{HO_CLEARING}", 'D', amount, reason))

        # Finalizing File 3 (Adding Total Debit line per branch)
        for branch_pfx, total_net in total_net_per_branch.items():
            if total_net > 0:
                file3_data.insert(0, (f"{branch_pfx}-{HO_CLEARING}", 'D', round(total_net, 2)))

        self._validate_balanced_entries(
            [(key[0], key[1], round(amount, 2)) for key, amount in file2_aggregated.items()],
            "Cost Center Bulk upload",
        )

        # --- Generate ZIP with 3 Excels ---
        zip_buffer = io.BytesIO()
        try:
            with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                safe_batch_name = (batch.name or 'Batch').replace('/', '_').replace('\\', '_')

                # FILE 1: PL misre finance
                out1, wb1, st1, mon1 = self._create_xls_workbook()
                ws1 = wb1.add_sheet('PL misre finance')
                for r, row_data in enumerate(file1_data):
                    ws1.write(r, 0, row_data[0], st1)
                    ws1.write(r, 1, row_data[1], st1)
                    ws1.write(r, 2, row_data[2], mon1)
                    ws1.write(r, 3, self._truncate_description(row_data[3]), st1)
                zip_file.writestr(f"FIN_UP {safe_batch_name[:23]}.xls", self._save_xls_workbook(wb1, out1))

                # FILE 2: Cost Center Bulk upload
                out2, wb2, st2 = self._create_cost_center_workbook()
                ws2 = self._prepare_cost_center_sheet(wb2)
                # Sorted File 2 data
                sorted_f2_keys = sorted(file2_aggregated.keys())
                for r, key in enumerate(sorted_f2_keys):
                    amt = file2_aggregated[key]
                    ws2.row(r).height = 300
                    ws2.write(r, 0, key[0], st2) # 9999-GL
                    ws2.write(r, 1, key[1], st2) # D
                    ws2.write(r, 2, amt, st2)    # Amount
                    ws2.write(r, 3, key[2], st2) # Dept CC
                    ws2.write(r, 4, key[3], st2) # Reason
                    ws2.write(r, 5, self._format_branch_cost_center_value(key[4]), st2) # HO Prefix / Branch Prefix
                zip_file.writestr(f"Cost Center Bulk upload {safe_batch_name}.xls", self._save_xls_workbook(wb2, out2))

                # FILE 3: Salary Bulk Upload
                out3, wb3, st3, mon3 = self._create_xls_workbook()
                ws3 = wb3.add_sheet('Salary Bulk Upload')
                for r, row_data in enumerate(file3_data):
                    ws3.write(r, 0, row_data[0], st3)
                    ws3.write(r, 1, row_data[1], st3)
                    ws3.write(r, 2, row_data[2], mon3)
                zip_file.writestr(f"Salary Bulk Upload {safe_batch_name}.xls", self._save_xls_workbook(wb3, out3))

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

    @http.route('/ahadu_payroll/backpay_batch_upload/<int:batch_id>', type='http', auth='user')
    def download_backpay_batch_upload(self, batch_id, **kw):
        batch = request.env['ahadu.backpay.batch'].browse(batch_id)
        if not batch.exists() or batch.state != 'approved':
            raise UserError("You cannot generate the Batch Upload files until the backpay batch is Approved.")

        # Data structures for the 3 files
        file1_data = [] # PL misre finance (Aggregated Deductions)
        file2_data = [] # Cost Center Bulk upload (Breakdown Earnings)
        file3_data = [] # Salary Bulk Upload (Individual Transfers)

        month_label = dict(batch._fields['month'].selection).get(batch.month, '')
        month_year = f"{month_label} {batch.year}"
        
        # Aggregation buckets
        file1_aggregated = defaultdict(float) 
        file2_aggregated = defaultdict(float) 
        total_net_per_branch = defaultdict(float)
        
        HO_CLEARING = '1040309'

        for line in batch.line_ids:
            emp = line.employee_id
            emp_type = emp.ahadu_employee_type_id.code or 'N/A'
            emp_type_name = 'clerical staff' if emp_type == 'CL_STAFF' else 'non clerical staff'
            branch = emp.branch_id
            branch_code = branch.cost_center_id.code or '0000'
            is_ho = branch.name == 'Head Office' or branch_code == '9999'
            is_addis = bool((branch.region_id and branch.region_id.name and branch.region_id.name.lower() == 'addis ababa') or \
                            (emp.region_id and emp.region_id.name and emp.region_id.name.lower() == 'addis ababa'))
            
            branch_prefix = '9999' if is_ho else str(branch_code)
            c_prefix = '9999' if (is_ho or is_addis) else branch_prefix
            
            dept_cc = str(emp.contract_id.cost_center_id.code or branch_prefix)
            if is_ho and '-' in dept_cc:
                dept_cc = dept_cc.replace('-', '')
            dept_cc = self._format_cost_center_code(dept_cc)

            # Earnings (Debit side for File 2)
            earnings = [
                ('BASIC', round(line.new_basic - line.old_basic, 2)),
                ('TRANS', round(line.new_transport - line.old_transport, 2)),
                ('REP', round(line.new_representation - line.old_representation, 2)),
                ('HOUSE', round(line.new_housing - line.old_housing, 2)),
                ('MOBILE', round(line.new_mobile - line.old_mobile, 2)),
                ('HARDSHIP', round(line.new_hardship - line.old_hardship, 2)),
                ('OT', round(line.new_ot - line.old_ot, 2)),
                ('PENSION_COMP', round(line.new_pension_comp - line.old_pension_comp, 2)),
            ]
            
            for code, amount in earnings:
                if amount <= 0: continue
                gl = self._get_finance_gl(code, emp_type, side='D')
                reason = f"backpay {emp_type_name} {code.lower()} {month_year}"
                file2_aggregated[(f"{branch_prefix}-{gl}", 'D', dept_cc, reason, branch_prefix)] += amount

            # Deductions (Credit side for File 1 aggregation)
            deductions = [
                ('TAX', round(line.new_income_tax - line.old_income_tax, 2)),
                ('PENSION_EMP', round(line.new_pension_emp - line.old_pension_emp, 2)),
                ('PENSION_COMP', round(line.new_pension_comp - line.old_pension_comp, 2)),
            ]
            
            for code, amount in deductions:
                if amount <= 0: continue
                gl = self._get_finance_gl(code, emp_type, side='C')
                
                if code in ['PENSION_EMP', 'PENSION_COMP']:
                    reason_f1 = f"PENSION 18PER {'HO staff' if is_ho else 'branch staff'} backpay {month_year}"
                    reason_f2 = f"PENSION 18PER backpay for {month_year}"
                elif code == 'TAX':
                    reason_f1 = f"EIT {'HO staff' if is_ho else 'branch staff'} backpay {month_year}"
                    reason_f2 = f"EIT backpay for {month_year}"
                else:
                    reason_f1 = f"backpay {code.lower()} {'HO staff' if is_ho else 'branch staff'} {month_year}"
                    reason_f2 = f"backpay {code.lower()} {month_year}"
                    
                file1_aggregated[(branch_prefix, c_prefix, gl, 'C', reason_f1)] += abs(amount)
                file2_aggregated[(f"{branch_prefix}-{HO_CLEARING}", 'C', '', reason_f2, '')] += abs(amount)

            # File 3: Individual Transfers
            diff_net = round(line.new_net - line.old_net, 2)
            if diff_net > 0:
                acc = line.bank_account or self._get_bank_account(emp, 'salary') or 'N/A'
                file3_data.append((acc, 'C', diff_net))
                total_net_per_branch[branch_prefix] += diff_net
                
                reason_f2 = f"BACKPAY NET SALARY {month_year}"
                file2_aggregated[(f"{branch_prefix}-{HO_CLEARING}", 'C', '', reason_f2, '')] += diff_net

        # Finalizing File 1
        for (d_prefix, c_prefix, gl, dc, reason), amount in file1_aggregated.items():
            file1_data.append((f"{c_prefix}-{gl}", 'C', amount, reason))
            file1_data.append((f"{d_prefix}-{HO_CLEARING}", 'D', amount, reason))

        # Finalizing File 3
        for branch_pfx, total_net in total_net_per_branch.items():
            if total_net > 0:
                file3_data.insert(0, (f"{branch_pfx}-{HO_CLEARING}", 'D', round(total_net, 2)))

        self._validate_balanced_entries(
            [(key[0], key[1], round(amount, 2)) for key, amount in file2_aggregated.items()],
            "Cost Center Bulk upload",
        )

        # --- Generate ZIP with 3 Excels ---
        zip_buffer = io.BytesIO()
        try:
            with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                safe_batch_name = (batch.name or 'Backpay').replace('/', '_').replace('\\', '_')

                # FILE 1: PL misre finance
                out1, wb1, st1, mon1 = self._create_xls_workbook()
                ws1 = wb1.add_sheet('PL misre finance')
                for r, row_data in enumerate(file1_data):
                    ws1.write(r, 0, row_data[0], st1)
                    ws1.write(r, 1, row_data[1], st1)
                    ws1.write(r, 2, row_data[2], mon1)
                    ws1.write(r, 3, self._truncate_description(row_data[3]), st1)
                zip_file.writestr(f"FIN_UP {safe_batch_name[:23]}.xls", self._save_xls_workbook(wb1, out1))

                # FILE 2: Cost Center Bulk upload
                out2, wb2, st2 = self._create_cost_center_workbook()
                ws2 = self._prepare_cost_center_sheet(wb2)
                sorted_f2_keys = sorted(file2_aggregated.keys())
                for r, key in enumerate(sorted_f2_keys):
                    amt = file2_aggregated[key]
                    ws2.row(r).height = 300
                    ws2.write(r, 0, key[0], st2) 
                    ws2.write(r, 1, key[1], st2) 
                    ws2.write(r, 2, amt, st2)    
                    ws2.write(r, 3, key[2], st2) 
                    ws2.write(r, 4, key[3], st2) 
                    ws2.write(r, 5, self._format_branch_cost_center_value(key[4]), st2) 
                zip_file.writestr(f"Cost Center Bulk upload {safe_batch_name}.xls", self._save_xls_workbook(wb2, out2))

                # FILE 3: Salary Bulk Upload
                out3, wb3, st3, mon3 = self._create_xls_workbook()
                ws3 = wb3.add_sheet('Salary Bulk Upload')
                for r, row_data in enumerate(file3_data):
                    ws3.write(r, 0, row_data[0], st3)
                    ws3.write(r, 1, row_data[1], st3)
                    ws3.write(r, 2, row_data[2], mon3)
                zip_file.writestr(f"Salary Bulk Upload {safe_batch_name}.xls", self._save_xls_workbook(wb3, out3))

        except Exception as e:
            _logger.error(f"Backpay CBS Batch Upload Generation Failed: {str(e)}")
            raise UserError(f"Generation failed: {str(e)}")

        zip_buffer.seek(0)
        zip_filename = f"CBS_Backpay_Upload_{safe_batch_name}.zip"
        quoted_filename = urllib.parse.quote(zip_filename)
        headers = [
            ('Content-Type', 'application/zip'),
            ('Content-Disposition', f'attachment; filename*=UTF-8\'\'{quoted_filename}'),
            ('Cache-Control', 'no-cache, no-store, must-revalidate'),
        ]
        return request.make_response(zip_buffer.getvalue(), headers=headers)

    @http.route('/ahadu_payroll/termination_batch_upload/<int:batch_id>', type='http', auth='user')
    def download_termination_batch_upload(self, batch_id, **kw):
        batch = request.env['hr.termination.run'].browse(batch_id)
        if not batch.exists() or batch.state not in ['calculated', 'done']:
            raise UserError("You cannot generate the Batch Upload files until the termination batch is Verified or Closed.")

        # Data structures for the 3 files
        file1_data = [] # PL misre finance (Aggregated Deductions)
        file2_data = [] # Cost Center Bulk upload (Breakdown Earnings)
        file3_data = [] # Salary Bulk Upload (Individual Transfers)

        month_year = batch.date_start.strftime('%b %Y') if batch.date_start else ''
        
        # Aggregation buckets
        file1_aggregated = defaultdict(float) 
        file2_aggregated = defaultdict(float) 
        total_net_per_branch = defaultdict(float)
        
        HO_CLEARING = '1040309'

        for slip in batch.slip_ids.filtered(lambda s: s.state != 'cancel'):
            emp = slip.employee_id
            emp_type = emp.ahadu_employee_type_id.code or 'N/A'
            emp_type_name = 'clerical staff' if emp_type == 'CL_STAFF' else 'non clerical staff'
            branch = emp.branch_id
            branch_code = branch.cost_center_id.code or '0000'
            is_ho = branch.name == 'Head Office' or branch_code == '9999'
            is_addis = bool((branch.region_id and branch.region_id.name and branch.region_id.name.lower() == 'addis ababa') or \
                            (emp.region_id and emp.region_id.name and emp.region_id.name.lower() == 'addis ababa'))
            
            branch_prefix = '9999' if is_ho else str(branch_code)
            c_prefix = '9999' if (is_ho or is_addis) else branch_prefix
            
            dept_cc = str(emp.contract_id.cost_center_id.code or branch_prefix)
            if is_ho and '-' in dept_cc:
                dept_cc = dept_cc.replace('-', '')
            dept_cc = self._format_cost_center_code(dept_cc)

            # Earnings (Debit side for File 2)
            earnings = [
                ('BASIC', slip.unpaid_salary),
                ('TRANS', slip.unpaid_transport),
                ('HOUSE', slip.unpaid_housing),
                ('MOBILE', slip.unpaid_mobile),
                ('REP', slip.representation_allowance),
                ('HARDSHIP', slip.unpaid_hardship),
                ('PENSION_COMP', slip.pension_comp),
            ]
            
            for code, amount in earnings:
                if amount <= 0: continue
                gl = self._get_finance_gl(code, emp_type, side='D')
                reason = f"termination {emp_type_name} {code.lower()} {month_year}"
                file2_aggregated[(f"{branch_prefix}-{gl}", 'D', dept_cc, reason, branch_prefix)] += amount

            # Special case for Leave Pay with specific GL and empty CCs
            if slip.leave_pay_gross > 0:
                gl = '2020217'
                reason = f"termination {emp_type_name} leave_pay {month_year}"
                file2_aggregated[(gl, 'D', '', reason, '')] += slip.leave_pay_gross

            # Deductions (Credit side for File 1 aggregation)
            pension_total = slip.pension_emp + slip.pension_comp
            deductions = [
                ('TAX', slip.grand_tax),
                ('PENSION_EMP', pension_total), 
            ]
            
            for code, amount in deductions:
                if amount <= 0: continue
                gl = self._get_finance_gl(code, emp_type, side='C')
                
                if code == 'PENSION_EMP':
                    reason_f1 = f"PENSION 18PER {'HO staff' if is_ho else 'branch staff'} termination {month_year}"
                    reason_f2 = f"PENSION 18PER termination for {month_year}"
                elif code == 'TAX':
                    reason_f1 = f"EIT {'HO staff' if is_ho else 'branch staff'} termination {month_year}"
                    reason_f2 = f"EIT termination for {month_year}"
                else:
                    reason_f1 = f"termination {code.lower()} {'HO staff' if is_ho else 'branch staff'} {month_year}"
                    reason_f2 = f"termination {code.lower()} {month_year}"
                    
                file1_aggregated[(branch_prefix, c_prefix, gl, 'C', reason_f1)] += abs(amount)
                file2_aggregated[(f"{branch_prefix}-{HO_CLEARING}", 'C', '', reason_f2, '')] += abs(amount)

            # Penalties/Other (Splitting Lost ID Card, VAT on ID Card and Other Deductions)
            if slip.lost_id_card > 0:
                reason_lost_id = f"termination lost id card {month_year}"
                file1_aggregated[(branch_prefix, c_prefix, '4050011', 'C', reason_lost_id)] += abs(slip.lost_id_card)
                file2_aggregated[(f"{branch_prefix}-{HO_CLEARING}", 'C', '', reason_lost_id, '')] += abs(slip.lost_id_card)

            if slip.vat_on_id_card > 0:
                reason_vat = f"termination id card vat {month_year}"
                file1_aggregated[(branch_prefix, c_prefix, '2020305', 'C', reason_vat)] += abs(slip.vat_on_id_card)
                file2_aggregated[(f"{branch_prefix}-{HO_CLEARING}", 'C', '', reason_vat, '')] += abs(slip.vat_on_id_card)

            if slip.other_deductions > 0:
                reason_other = f"termination other deductions {month_year}"
                file1_aggregated[(branch_prefix, c_prefix, '4050012', 'C', reason_other)] += abs(slip.other_deductions)
                file2_aggregated[(f"{branch_prefix}-{HO_CLEARING}", 'C', '', reason_other, '')] += abs(slip.other_deductions)

            # File 3: Individual Transfers
            net = slip.net_payable
            if net > 0:
                acc = self._get_bank_account(emp, 'salary') or 'N/A'
                file3_data.append((acc, 'C', net))
                total_net_per_branch[branch_prefix] += net
                
                reason_f2 = f"TERMINATION NET SALARY {month_year}"
                file2_aggregated[(f"{branch_prefix}-{HO_CLEARING}", 'C', '', reason_f2, '')] += net

        # Finalizing File 1
        for (d_prefix, c_prefix, gl, dc, reason), amount in file1_aggregated.items():
            file1_data.append((f"{c_prefix}-{gl}", 'C', amount, reason))
            file1_data.append((f"{d_prefix}-{HO_CLEARING}", 'D', amount, reason))

        # Finalizing File 3
        for branch_pfx, total_net in total_net_per_branch.items():
            if total_net > 0:
                file3_data.insert(0, (f"{branch_pfx}-{HO_CLEARING}", 'D', round(total_net, 2)))

        self._validate_balanced_entries(
            [(key[0], key[1], round(amount, 2)) for key, amount in file2_aggregated.items()],
            "Cost Center Bulk upload",
        )

        # --- Generate ZIP with 3 Excels ---
        zip_buffer = io.BytesIO()
        try:
            with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                safe_batch_name = (batch.name or 'Termination').replace('/', '_').replace('\\', '_')

                # FILE 1: PL misre finance
                out1, wb1, st1, mon1 = self._create_xls_workbook()
                ws1 = wb1.add_sheet('PL misre finance')
                for r, row_data in enumerate(file1_data):
                    ws1.write(r, 0, row_data[0], st1)
                    ws1.write(r, 1, row_data[1], st1)
                    ws1.write(r, 2, row_data[2], mon1)
                    ws1.write(r, 3, self._truncate_description(row_data[3]), st1)
                zip_file.writestr(f"FIN_UP {safe_batch_name[:23]}.xls", self._save_xls_workbook(wb1, out1))

                # FILE 2: Cost Center Bulk upload
                out2, wb2, st2 = self._create_cost_center_workbook()
                ws2 = self._prepare_cost_center_sheet(wb2)
                sorted_f2_keys = sorted(file2_aggregated.keys())
                for r, key in enumerate(sorted_f2_keys):
                    amt = file2_aggregated[key]
                    ws2.row(r).height = 300
                    ws2.write(r, 0, key[0], st2) 
                    ws2.write(r, 1, key[1], st2) 
                    ws2.write(r, 2, amt, st2)    
                    ws2.write(r, 3, key[2], st2) 
                    ws2.write(r, 4, key[3], st2) 
                    ws2.write(r, 5, self._format_branch_cost_center_value(key[4]), st2) 
                zip_file.writestr(f"Cost Center Bulk upload {safe_batch_name}.xls", self._save_xls_workbook(wb2, out2))

                # FILE 3: Salary Bulk Upload
                out3, wb3, st3, mon3 = self._create_xls_workbook()
                ws3 = wb3.add_sheet('Salary Bulk Upload')
                for r, row_data in enumerate(file3_data):
                    ws3.write(r, 0, row_data[0], st3)
                    ws3.write(r, 1, row_data[1], st3)
                    ws3.write(r, 2, row_data[2], mon3)
                zip_file.writestr(f"Salary Bulk Upload {safe_batch_name}.xls", self._save_xls_workbook(wb3, out3))

        except Exception as e:
            _logger.error(f"Termination CBS Batch Upload Generation Failed: {str(e)}")
            raise UserError(f"Generation failed: {str(e)}")

        zip_buffer.seek(0)
        zip_filename = f"CBS_Termination_Upload_{safe_batch_name}.zip"
        quoted_filename = urllib.parse.quote(zip_filename)
        headers = [
            ('Content-Type', 'application/zip'),
            ('Content-Disposition', f'attachment; filename*=UTF-8\'\'{quoted_filename}'),
            ('Cache-Control', 'no-cache, no-store, must-revalidate'),
        ]
        return request.make_response(zip_buffer.getvalue(), headers=headers)

    @http.route('/ahadu_payroll/resignation_batch_upload/<int:batch_id>', type='http', auth='user')
    def download_resignation_batch_upload(self, batch_id, **kw):
        batch = request.env['hr.resignation.run'].browse(batch_id)
        if not batch.exists() or batch.state not in ['calculated', 'done']:
            raise UserError("You cannot generate the Batch Upload files until the resignation batch is Verified or Closed.")

        # Data structures for the 3 files
        file1_data = [] # PL misre finance (Aggregated Deductions)
        file2_data = [] # Cost Center Bulk upload (Breakdown Earnings)
        file3_data = [] # Salary Bulk Upload (Individual Transfers)

        month_year = batch.date_start.strftime('%b %Y') if batch.date_start else ''
        
        # Aggregation buckets
        file1_aggregated = defaultdict(float) 
        file2_aggregated = defaultdict(float) 
        total_net_per_branch = defaultdict(float)
        
        HO_CLEARING = '1040309'

        for slip in batch.slip_ids.filtered(lambda s: s.state != 'cancel'):
            emp = slip.employee_id
            emp_type = emp.ahadu_employee_type_id.code or 'N/A'
            emp_type_name = 'clerical staff' if emp_type == 'CL_STAFF' else 'non clerical staff'
            branch = emp.branch_id
            branch_code = branch.cost_center_id.code or '0000'
            is_ho = branch.name == 'Head Office' or branch_code == '9999'
            is_addis = bool((branch.region_id and branch.region_id.name and branch.region_id.name.lower() == 'addis ababa') or \
                            (emp.region_id and emp.region_id.name and emp.region_id.name.lower() == 'addis ababa'))
            
            branch_prefix = '9999' if is_ho else str(branch_code)
            c_prefix = '9999' if (is_ho or is_addis) else branch_prefix
            
            dept_cc = str(emp.contract_id.cost_center_id.code or branch_prefix)
            if is_ho and '-' in dept_cc:
                dept_cc = dept_cc.replace('-', '')
            dept_cc = self._format_cost_center_code(dept_cc)

            # Earnings (Debit side for File 2)
            earnings = [
                ('BASIC', slip.unpaid_salary),
                ('TRANS', slip.unpaid_transport),
                ('HOUSE', slip.unpaid_housing),
                ('MOBILE', slip.unpaid_mobile),
                ('REP', slip.representation_allowance),
                ('PENSION_COMP', slip.pension_comp),
            ]
            
            for code, amount in earnings:
                if amount <= 0: continue
                gl = self._get_finance_gl(code, emp_type, side='D')
                reason = f"resignation {emp_type_name} {code.lower()} {month_year}"
                file2_aggregated[(f"{branch_prefix}-{gl}", 'D', dept_cc, reason, branch_prefix)] += amount

            # Special case for Leave Pay with specific GL and empty CCs
            if slip.leave_pay_gross > 0:
                gl = '2020217'
                reason = f"resignation {emp_type_name} leave_pay {month_year}"
                file2_aggregated[(gl, 'D', '', reason, '')] += slip.leave_pay_gross

            # Deductions (Credit side for File 1 aggregation)
            pension_total = slip.pension_emp + slip.pension_comp
            deductions = [
                ('TAX', slip.grand_tax),
                ('PENSION_EMP', pension_total), 
            ]
            
            for code, amount in deductions:
                if amount <= 0: continue
                gl = self._get_finance_gl(code, emp_type, side='C')
                
                if code == 'PENSION_EMP':
                    reason_f1 = f"PENSION 18PER {'HO staff' if is_ho else 'branch staff'} resignation {month_year}"
                    reason_f2 = f"PENSION 18PER resignation for {month_year}"
                elif code == 'TAX':
                    reason_f1 = f"EIT {'HO staff' if is_ho else 'branch staff'} resignation {month_year}"
                    reason_f2 = f"EIT resignation for {month_year}"
                else:
                    reason_f1 = f"resignation {code.lower()} {'HO staff' if is_ho else 'branch staff'} {month_year}"
                    reason_f2 = f"resignation {code.lower()} {month_year}"
                    
                file1_aggregated[(branch_prefix, c_prefix, gl, 'C', reason_f1)] += abs(amount)
                file2_aggregated[(f"{branch_prefix}-{HO_CLEARING}", 'C', '', reason_f2, '')] += abs(amount)

            # Penalties/Other (Splitting Lost ID Card, VAT on ID Card and Other Deductions)
            if slip.lost_id_card > 0:
                reason_lost_id = f"resignation lost id card {month_year}"
                file1_aggregated[(branch_prefix, c_prefix, '4050011', 'C', reason_lost_id)] += abs(slip.lost_id_card)
                file2_aggregated[(f"{branch_prefix}-{HO_CLEARING}", 'C', '', reason_lost_id, '')] += abs(slip.lost_id_card)

            if slip.vat_on_id_card > 0:
                reason_vat = f"resignation id card vat {month_year}"
                file1_aggregated[(branch_prefix, c_prefix, '2020305', 'C', reason_vat)] += abs(slip.vat_on_id_card)
                file2_aggregated[(f"{branch_prefix}-{HO_CLEARING}", 'C', '', reason_vat, '')] += abs(slip.vat_on_id_card)

            if slip.other_deductions > 0:
                reason_other = f"resignation other deductions {month_year}"
                file1_aggregated[(branch_prefix, c_prefix, '4050012', 'C', reason_other)] += abs(slip.other_deductions)
                file2_aggregated[(f"{branch_prefix}-{HO_CLEARING}", 'C', '', reason_other, '')] += abs(slip.other_deductions)

            # File 3: Individual Transfers
            net = slip.net_payable
            if net > 0:
                acc = slip.credit_account_number or self._get_bank_account(emp, 'salary') or 'N/A'
                file3_data.append((acc, 'C', net))
                total_net_per_branch[branch_prefix] += net
                
                reason_f2 = f"RESIGNATION NET SALARY {month_year}"
                file2_aggregated[(f"{branch_prefix}-{HO_CLEARING}", 'C', '', reason_f2, '')] += net

        # Finalizing File 1
        for (d_prefix, c_prefix, gl, dc, reason), amount in file1_aggregated.items():
            file1_data.append((f"{c_prefix}-{gl}", 'C', amount, reason))
            file1_data.append((f"{d_prefix}-{HO_CLEARING}", 'D', amount, reason))

        # Finalizing File 3
        for branch_pfx, total_net in total_net_per_branch.items():
            if total_net > 0:
                file3_data.insert(0, (f"{branch_pfx}-{HO_CLEARING}", 'D', round(total_net, 2)))

        self._validate_balanced_entries(
            [(key[0], key[1], round(amount, 2)) for key, amount in file2_aggregated.items()],
            "Cost Center Bulk upload",
        )

        # --- Generate ZIP with 3 Excels ---
        zip_buffer = io.BytesIO()
        try:
            with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                safe_batch_name = (batch.name or 'Resignation').replace('/', '_').replace('\\', '_')

                # FILE 1: PL misre finance
                out1, wb1, st1, mon1 = self._create_xls_workbook()
                ws1 = wb1.add_sheet('PL misre finance')
                for r, row_data in enumerate(file1_data):
                    ws1.write(r, 0, row_data[0], st1)
                    ws1.write(r, 1, row_data[1], st1)
                    ws1.write(r, 2, row_data[2], mon1)
                    ws1.write(r, 3, self._truncate_description(row_data[3]), st1)
                zip_file.writestr(f"FIN_UP {safe_batch_name[:23]}.xls", self._save_xls_workbook(wb1, out1))

                # FILE 2: Cost Center Bulk upload
                out2, wb2, st2 = self._create_cost_center_workbook()
                ws2 = self._prepare_cost_center_sheet(wb2)
                sorted_f2_keys = sorted(file2_aggregated.keys())
                for r, key in enumerate(sorted_f2_keys):
                    amt = file2_aggregated[key]
                    ws2.row(r).height = 300
                    ws2.write(r, 0, key[0], st2) 
                    ws2.write(r, 1, key[1], st2) 
                    ws2.write(r, 2, amt, st2)    
                    ws2.write(r, 3, key[2], st2) 
                    ws2.write(r, 4, key[3], st2) 
                    ws2.write(r, 5, self._format_branch_cost_center_value(key[4]), st2) 
                zip_file.writestr(f"Cost Center Bulk upload {safe_batch_name}.xls", self._save_xls_workbook(wb2, out2))

                # FILE 3: Salary Bulk Upload
                out3, wb3, st3, mon3 = self._create_xls_workbook()
                ws3 = wb3.add_sheet('Salary Bulk Upload')
                for r, row_data in enumerate(file3_data):
                    ws3.write(r, 0, row_data[0], st3)
                    ws3.write(r, 1, row_data[1], st3)
                    ws3.write(r, 2, row_data[2], mon3)
                zip_file.writestr(f"Salary Bulk Upload {safe_batch_name}.xls", self._save_xls_workbook(wb3, out3))

        except Exception as e:
            _logger.error(f"Resignation CBS Batch Upload Generation Failed: {str(e)}")
            raise UserError(f"Generation failed: {str(e)}")

        zip_buffer.seek(0)
        zip_filename = f"CBS_Resignation_Upload_{safe_batch_name}.zip"
        quoted_filename = urllib.parse.quote(zip_filename)
        headers = [
            ('Content-Type', 'application/zip'),
            ('Content-Disposition', f'attachment; filename*=UTF-8\'\'{quoted_filename}'),
            ('Cache-Control', 'no-cache, no-store, must-revalidate'),
        ]
        return request.make_response(zip_buffer.getvalue(), headers=headers)
