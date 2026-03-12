# -*- coding: utf-8 -*-
import io
import os
import logging
from odoo import http, fields
from odoo.http import request
from odoo.tools.misc import xlsxwriter
from odoo.tools import file_path
from .common import AhaduReportCommon

_logger = logging.getLogger(__name__)

class PayrollSheetReport(AhaduReportCommon):
    
    @http.route('/ahadu_payroll/payroll_sheet_excel/<int:batch_id>', type='http', auth='user')
    def download_payroll_sheet_excel(self, batch_id, **kw):
        batch = request.env['hr.payslip.run'].browse(batch_id)
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Payroll Sheet')
        
        # Formats
        title_fmt = workbook.add_format({'bold': True, 'size': 14, 'align': 'center', 'valign': 'vcenter'})
        subtitle_fmt = workbook.add_format({'bold': True, 'size': 11, 'align': 'center', 'valign': 'vcenter'})
        branch_fmt = workbook.add_format({'bold': True, 'size': 10, 'align': 'center', 'valign': 'vcenter', 'italic': True})
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#840036', 'font_color': 'white', 'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True, 'font_size': 9})
        data_fmt = workbook.add_format({'border': 1, 'font_size': 9})
        money_fmt = workbook.add_format({'num_format': '#,##0.00', 'border': 1, 'font_size': 9})
        total_header_fmt = workbook.add_format({'bold': True, 'bg_color': '#850037', 'font_color': 'white', 'border': 1, 'align': 'right', 'font_size': 9})
        total_money_fmt = workbook.add_format({'bold': True, 'bg_color': '#850037', 'font_color': 'white', 'num_format': '#,##0.00', 'border': 1, 'font_size': 9})
        summary_title_fmt = workbook.add_format({'bold': True, 'bg_color': '#f2f2f2', 'border': 1, 'align': 'center', 'font_size': 10})
        border_fmt = workbook.add_format({'border': 1, 'font_size': 9})

        # Header with Logo
        try:
            # Get logo path using Odoo 18 standards
            image_path = file_path('ahadu_payroll/src/images/Ahadu Bank Logo with Name.jpg')
            
            if image_path and os.path.exists(image_path):
                # Set row heights for header area
                worksheet.set_row(0, 60)  # Logo row - taller for better logo display
                worksheet.set_row(1, 20)  # Title row
                worksheet.set_row(2, 18)  # Month row
                worksheet.set_row(3, 18)  # Branch row
                
                # Row 1: Logo centered across all columns (A1:AH1)
                worksheet.merge_range('A1:AH1', '')
                # Insert logo centered - larger scale to fit the space better
                worksheet.insert_image('A1', image_path, {
                    'x_scale': 0.8, 
                    'y_scale': 0.8, 
                    'x_offset': 400,  # Adjusted center
                    'y_offset': 5
                })
                
                # Row 2: Title (A2:AK2)
                worksheet.merge_range('A2:AK2', 'Ahadu Bank S.C - Employee Payroll Sheet', title_fmt)
                
                # Row 3: Month (A3:AK3)
                month_name = batch.date_start.strftime('%B %Y') if batch.date_start else ''
                worksheet.merge_range('A3:AK3', f'For the Month of {month_name}', subtitle_fmt)
                
                # Row 4: Filters (A4:AH4)
                filter_texts = []
                
                # 1. Branch filters
                if batch.branch_ids:
                    if len(batch.branch_ids) == 1:
                        filter_texts.append(f"Branch: {batch.branch_ids[0].name}")
                    else:
                        filter_texts.append(f"Branches: {', '.join(batch.branch_ids.mapped('name'))}")
                elif batch.branch_id:
                    filter_texts.append(f"Branch: {batch.branch_id.name}")
                
                # 2. Pay Group filters
                if batch.pay_group_ids:
                    filter_texts.append(f"Pay Groups: {', '.join(batch.pay_group_ids.mapped('name'))}")
                
                # 3. Region filters
                if batch.region_ids:
                    filter_texts.append(f"Regions: {', '.join(batch.region_ids.mapped('name'))}")
                
                # 4. Cost Center filters
                if batch.cost_center_ids:
                    filter_texts.append(f"Cost Centers: {', '.join(batch.cost_center_ids.mapped('name'))}")

                filter_info = " | ".join(filter_texts) if filter_texts else ""
                worksheet.merge_range('A4:AE4', filter_info, branch_fmt)
            else:
                # Fallback if logo not found
                worksheet.merge_range('A1:AE1', 'Ahadu Bank S.C - Employee Payroll Sheet', title_fmt)
                month_name = batch.date_start.strftime('%B %Y') if batch.date_start else ''
                worksheet.merge_range('A2:AE2', f'For the Month of {month_name}', subtitle_fmt)
                
                # Filters fallback
                filter_texts = []
                if batch.branch_ids:
                    filter_texts.append(f"Branches: {', '.join(batch.branch_ids.mapped('name'))}")
                elif batch.branch_id:
                    filter_texts.append(f"Branch: {batch.branch_id.name}")
                
                if batch.pay_group_ids:
                    filter_texts.append(f"Pay Groups: {', '.join(batch.pay_group_ids.mapped('name'))}")

                filter_info = " | ".join(filter_texts) if filter_texts else ""
                worksheet.merge_range('A3:AK3', filter_info, branch_fmt)
        except Exception as e:
            _logger.error(f"Failed to generate report header: {str(e)}")
            # Error already logged, will proceed with standard headers
            filter_info = "Error in header generation"
            # Do NOT call merge_range here to avoid OverlappingRange error

        # Headers (now starting at row 6, index 5)
        headers = [
            'SN', 'Employee Name', 'Dept / Branch', 'Emp ID', 'Joining Date', 'TIN', 
            'Basic Salary', 'Liter', 'Fuel Rate', 'Trans. Allow.', 'Taxable Trans.', 
            'Representation', 'Hardship', 'Housing', 'Mobile', 
            'Cash Indemnity', 'Cash Indemnity to Cash Ind A/C', 'Cash Indemnity to S/A', 
            'OT', 'Gross Salary & Ben.', 'Taxable Income', 
            'Pension (11%)', 'Income Tax', 'Pension (7%)', 
            'Adv. Loan', 'Pers. Loan', 'Other Loans', 'Other Ded.', 'Cost Sharing', 'Penalty', 'Loss of Pay', 
            'Total Ded.', 'Net Income', 
            'Bank Account', 'Adv Loan Acc', 'Pers Loan Acc', 'Cash Ind Acc'
        ]
        
        group_header_title_fmt = workbook.add_format({'bold': True, 'font_size': 12, 'align': 'center', 'valign': 'vcenter', 'color': '#840036', 'underline': True})
        
        fuel_price_global = float(request.env['ir.config_parameter'].sudo().get_param('ahadu_hr.fuel_price_per_liter', 0.0))
        
        all_slips = list(self._get_payslip_lines(batch))
        clerical_slips = [s for s in all_slips if s.employee_id.ahadu_employee_type_id.code == 'CL_STAFF']
        non_clerical_slips = [s for s in all_slips if s.employee_id.ahadu_employee_type_id.code == 'NON_CL']
        other_slips = [s for s in all_slips if s.employee_id.ahadu_employee_type_id.code not in ['CL_STAFF', 'NON_CL']]

        def write_section(title, slips, start_row, start_seq, global_sums):
            if not slips:
                return start_row, start_seq

            # 1. Section Title (Centered Outside Table)
            worksheet.merge_range(start_row, 0, start_row, 36, title, group_header_title_fmt)
            start_row += 1

            # 2. Table Headers
            for col, h in enumerate(headers): 
                worksheet.write(start_row, col, h, header_fmt)
                worksheet.set_column(col, col, 12 if col > 5 else 20)
            start_row += 1

            # 3. Initialize Section Sums
            section_sums = {k: 0.0 for k in sums.keys()}

            # 4. Write Data Rows
            # Reuse write_slips logic but specialized here to avoid complexity of passing too many args if we extracted it fully.
            # actually we can reuse write_slips if we pass section_sums.
            current_row = start_row
            current_seq = start_seq
            
            for slip in slips:
                employee = slip.employee_id
                fuel_rate = fuel_price_global
                
                # Bank Accounts
                bank_accounts = request.env['hr.employee.bank.account'].sudo().search([('employee_id', '=', employee.id)])
                salary_acc = bank_accounts.filtered(lambda a: a.account_type == 'salary')[:1].account_number or ''
                ci_acc = bank_accounts.filtered(lambda a: a.account_type == 'cash_indemnity')[:1].account_number or ''
                
                # Loan account(s)
                active_loans_adv = request.env['hr.loan'].sudo().search([
                    ('employee_id', '=', employee.id),
                    ('state', '=', 'approved'),
                    ('date_start', '<=', slip.date_to),
                    ('loan_type_id.name', '=', 'Emergency/Salary Advance Loan')
                ])
                active_loans_pers = request.env['hr.loan'].sudo().search([
                    ('employee_id', '=', employee.id),
                    ('state', '=', 'approved'),
                    ('date_start', '<=', slip.date_to),
                    ('loan_type_id.name', '=', 'Personal Staff Loan')
                ])
                
                adv_loan_acc = active_loans_adv[0].bank_account_id.account_number if active_loans_adv and active_loans_adv[0].bank_account_id else ''
                pers_loan_acc = active_loans_pers[0].bank_account_id.account_number if active_loans_pers and active_loans_pers[0].bank_account_id else ''
                
                # Fallbacks if none found
                if not adv_loan_acc and not pers_loan_acc:
                    # Generic fallback if no specific loan accounts found
                    gen_loan_acc = bank_accounts.filtered(lambda a: a.account_type == 'loan_settlement')[:1].account_number or ''
                    # If we don't have specific ones, maybe one of them is the generic one? 
                    # For now just leave as is or assign to pers?
                    pass
                
                
                
                trans_amt = self._get_rule_total(slip, 'TRANS')
                vals = {
                    'full_basic': employee.emp_wage, 
                    'basic': self._get_rule_total(slip, 'BASIC'), 
                    'trans': trans_amt, 
                    'tax_trans': max(0.0, trans_amt - slip._get_region_transport_exemption()), 
                    'rep': self._get_rule_total(slip, 'REP'), 
                    'house': self._get_rule_total(slip, 'HOUSE'), 
                    'hardship': self._get_rule_total(slip, 'HARDSHIP'), 
                    'cash_ind': self._get_rule_total(slip, 'CASH_IND'), 
                    'ci_gross': slip.cash_indemnity_allowance,
                    'ci_tax': slip.cash_indemnity_tax,
                    'ci_to_bal': slip.ci_to_balance,
                    'ci_to_sal': slip.ci_to_salary,
                    'mobile': self._get_rule_total(slip, 'MOBILE'), 
                    'other_alw': self._get_rule_total(slip, 'OTHER_BEN'), 
                    'lop_adj': self._get_rule_total(slip, 'LOP_ADJ'), 
                    'ot': slip.overtime_amount, 
                    'gross': self._get_rule_total(slip, 'GROSS'), 
                    't_income': slip._get_ahadu_taxable_gross(), 
                    'p_comp': self._get_rule_total(slip, 'PENSION_COMP'), 
                    'tax': self._get_rule_total(slip, 'TAX') + slip.cash_indemnity_tax, 
                    'p_emp': self._get_rule_total(slip, 'PENSION_EMP'), 
                    'adv_loan': slip._get_ahadu_advance_loan_deduction(), 
                    'pers_loan': slip._get_ahadu_personal_loan_deduction(), 
                    'other_loan': slip._get_ahadu_other_loan_deduction(), 
                    'savings': self._get_rule_total(slip, 'SAVINGS'), 
                    'credit_assoc': self._get_rule_total(slip, 'CREDIT_ASSOC'), 
                    'penalty': abs(self._get_rule_total(slip, 'PENALTY')), 
                    'lop_leave': self._get_rule_total(slip, 'LOP_LEAVE'), 
                    'other_ded': self._get_rule_total(slip, 'OTHER_DED'), 
                    'c_sharing': self._get_rule_total(slip, 'COST_SHARING'),
                    'total_ded': sum(slip.line_ids.filtered(lambda r: r.category_id.code == 'DED').mapped('total')), 
                    'net': self._get_rule_total(slip, 'NET')
                }
                
                worksheet.write(current_row, 0, current_seq, data_fmt)
                worksheet.write(current_row, 1, employee.name, data_fmt)
                
                dept_branch = ""
                branch_name = employee.branch_id.name or ""
                if branch_name.lower() == 'head office':
                    dept_branch = employee.department_id.name or branch_name
                else:
                    dept_branch = branch_name or (employee.department_id.name or "")
                worksheet.write(current_row, 2, dept_branch, data_fmt)
                worksheet.write(current_row, 3, employee.employee_id or '', data_fmt)
                worksheet.write(current_row, 4, slip.contract_id.date_start.strftime('%Y-%m-%d') if slip.contract_id.date_start else '', data_fmt)
                worksheet.write(current_row, 5, employee.tin_number or '', data_fmt)
                worksheet.write(current_row, 6, vals['basic'], money_fmt)
                worksheet.write(current_row, 7, employee.transport_allowance_liters, data_fmt)
                worksheet.write(current_row, 8, fuel_rate, money_fmt)
                worksheet.write(current_row, 9, vals['trans'], money_fmt)
                worksheet.write(current_row, 10, vals['tax_trans'], money_fmt)
                worksheet.write(current_row, 11, vals['rep'], money_fmt)
                worksheet.write(current_row, 12, vals['hardship'], money_fmt)
                worksheet.write(current_row, 13, vals['house'], money_fmt)
                worksheet.write(current_row, 14, vals['mobile'], money_fmt)
                worksheet.write(current_row, 15, vals['ci_gross'], money_fmt)
                worksheet.write(current_row, 16, vals['ci_to_bal'], money_fmt)
                worksheet.write(current_row, 17, vals['ci_to_sal'], money_fmt)
                worksheet.write(current_row, 18, vals['ot'], money_fmt)
                worksheet.write(current_row, 19, vals['gross'], money_fmt)
                worksheet.write(current_row, 20, vals['t_income'], money_fmt)
                worksheet.write(current_row, 21, vals['p_comp'], money_fmt)
                worksheet.write(current_row, 22, vals['tax'], money_fmt)
                worksheet.write(current_row, 23, vals['p_emp'], money_fmt)
                worksheet.write(current_row, 24, vals['adv_loan'], money_fmt)
                worksheet.write(current_row, 25, vals['pers_loan'], money_fmt)
                worksheet.write(current_row, 26, vals['other_loan'], money_fmt)
                worksheet.write(current_row, 27, vals['other_ded'], money_fmt)
                worksheet.write(current_row, 28, vals['c_sharing'], money_fmt)
                worksheet.write(current_row, 29, vals['penalty'], money_fmt)
                worksheet.write(current_row, 30, vals['lop_leave'], money_fmt)
                worksheet.write(current_row, 31, vals['total_ded'], money_fmt)
                worksheet.write(current_row, 32, vals['net'], money_fmt)
                worksheet.write(current_row, 33, salary_acc, data_fmt)
                worksheet.write(current_row, 34, adv_loan_acc, data_fmt)
                worksheet.write(current_row, 35, pers_loan_acc, data_fmt)
                worksheet.write(current_row, 36, ci_acc, data_fmt)
                
                for k in section_sums: 
                    section_sums[k] += vals[k]
                    
                current_row += 1; current_seq += 1

            # 5. Write Section Totals
            worksheet.merge_range(current_row, 0, current_row, 5, 'SECTION TOTALS:', total_header_fmt)
            worksheet.write(current_row, 6, section_sums['basic'], total_money_fmt)
            worksheet.write(current_row, 7, '', total_money_fmt)
            worksheet.write(current_row, 8, '', total_money_fmt)
            worksheet.write(current_row, 9, section_sums['trans'], total_money_fmt)
            worksheet.write(current_row, 10, section_sums['tax_trans'], total_money_fmt)
            worksheet.write(current_row, 11, section_sums['rep'], total_money_fmt)
            worksheet.write(current_row, 12, section_sums['hardship'], total_money_fmt)
            worksheet.write(current_row, 13, section_sums['house'], total_money_fmt)
            worksheet.write(current_row, 14, section_sums['mobile'], total_money_fmt)
            worksheet.write(current_row, 15, section_sums['ci_gross'], total_money_fmt)
            worksheet.write(current_row, 16, section_sums['ci_to_bal'], total_money_fmt)
            worksheet.write(current_row, 17, section_sums['ci_to_sal'], total_money_fmt)
            worksheet.write(current_row, 18, section_sums['ot'], total_money_fmt)
            worksheet.write(current_row, 19, section_sums['gross'], total_money_fmt)
            worksheet.write(current_row, 20, section_sums['t_income'], total_money_fmt)
            worksheet.write(current_row, 21, section_sums['p_comp'], total_money_fmt)
            worksheet.write(current_row, 22, section_sums['tax'], total_money_fmt)
            worksheet.write(current_row, 23, section_sums['p_emp'], total_money_fmt)
            worksheet.write(current_row, 24, section_sums['adv_loan'], total_money_fmt)
            worksheet.write(current_row, 25, section_sums['pers_loan'], total_money_fmt)
            worksheet.write(current_row, 26, section_sums['other_loan'], total_money_fmt)
            worksheet.write(current_row, 27, section_sums['other_ded'], total_money_fmt)
            worksheet.write(current_row, 28, section_sums['c_sharing'], total_money_fmt)
            worksheet.write(current_row, 29, section_sums['penalty'], total_money_fmt)
            worksheet.write(current_row, 30, section_sums['lop_leave'], total_money_fmt)
            worksheet.write(current_row, 31, section_sums['total_ded'], total_money_fmt)
            worksheet.write(current_row, 32, section_sums['net'], total_money_fmt)
            worksheet.merge_range(current_row, 33, current_row, 36, '', total_money_fmt)

            # Accumulate Global Sums
            for k in global_sums:
                global_sums[k] += section_sums[k]

            # 6. Spacing
            current_row += 3 # 1 for total + 2 for spacing
            return current_row, current_seq

        # Process each section
        row = 7; seq = 1
        sums = {k: 0.0 for k in ['full_basic', 'basic', 'trans', 'tax_trans', 'rep', 'house', 'hardship', 'cash_ind', 'ci_gross', 'ci_tax', 'ci_to_bal', 'ci_to_sal', 'mobile', 'other_alw', 'lop_adj', 'ot', 'gross', 't_income', 'p_comp', 'tax', 'p_emp', 'adv_loan', 'pers_loan', 'other_loan', 'savings', 'credit_assoc', 'penalty', 'lop_leave', 'other_ded', 'c_sharing', 'total_ded', 'net']}

        row, seq = write_section("PAYMENT OF SALARY FOR CLERICAL STAFFS", clerical_slips, row, seq, sums)
        row, seq = write_section("PAYMENT OF SALARY FOR NON CLERICAL STAFFS", non_clerical_slips, row, seq, sums)
        row, seq = write_section("PAYMENT OF SALARY FOR OTHER STAFFS", other_slips, row, seq, sums)
            
        # Grand Totals Row
        worksheet.merge_range(row, 0, row, 5, 'GRAND TOTALS:', total_header_fmt)
        worksheet.write(row, 6, sums['basic'], total_money_fmt)
        worksheet.write(row, 7, '', total_money_fmt)
        worksheet.write(row, 8, '', total_money_fmt)
        worksheet.write(row, 9, sums['trans'], total_money_fmt)
        worksheet.write(row, 10, sums['tax_trans'], total_money_fmt)
        worksheet.write(row, 11, sums['rep'], total_money_fmt)
        worksheet.write(row, 12, sums['hardship'], total_money_fmt)  # NEW: Hardship total
        worksheet.write(row, 13, sums['house'], total_money_fmt)
        worksheet.write(row, 14, sums['mobile'], total_money_fmt)
        # Cash Indemnity totals (15-17)
        worksheet.write(row, 15, sums['ci_gross'], total_money_fmt)
        worksheet.write(row, 16, sums['ci_to_bal'], total_money_fmt)
        worksheet.write(row, 17, sums['ci_to_sal'], total_money_fmt)
        # All subsequent columns shifted by +1 for hardship
        worksheet.write(row, 18, sums['ot'], total_money_fmt)
        worksheet.write(row, 19, sums['gross'], total_money_fmt)
        worksheet.write(row, 20, sums['t_income'], total_money_fmt)
        worksheet.write(row, 21, sums['p_comp'], total_money_fmt)
        worksheet.write(row, 22, sums['tax'], total_money_fmt)
        worksheet.write(row, 23, sums['p_emp'], total_money_fmt)
        worksheet.write(row, 24, sums['adv_loan'], total_money_fmt)
        worksheet.write(row, 25, sums['pers_loan'], total_money_fmt)
        worksheet.write(row, 26, sums['other_loan'], total_money_fmt)
        worksheet.write(row, 27, sums['other_ded'], total_money_fmt)
        worksheet.write(row, 28, sums['c_sharing'], total_money_fmt)
        worksheet.write(row, 29, sums['penalty'], total_money_fmt)
        worksheet.write(row, 30, sums['lop_leave'], total_money_fmt)
        worksheet.write(row, 31, sums['total_ded'], total_money_fmt)
        worksheet.write(row, 32, sums['net'], total_money_fmt)
        worksheet.merge_range(row, 33, row, 36, '', total_money_fmt)

        # Analysis Sections
        row += 3
        worksheet.merge_range(row, 1, row, 3, 'Debit Side Analysis', summary_title_fmt)
        worksheet.write(row + 1, 1, 'Description', summary_title_fmt)
        worksheet.write(row + 1, 2, 'GL Code', summary_title_fmt)
        worksheet.write(row + 1, 3, 'Amount', summary_title_fmt)
        
        debits = [
            ('Basic Salary (Full)', self._get_gl_codes('BASIC', 'debit'), sums['basic']), 
            ('Transportation Allowance', self._get_gl_codes('TRANS', 'debit'), sums['trans']), 
            ('Representation Allowance', self._get_gl_codes('REP', 'debit'), sums['rep']), 
            ('Housing Allowance', self._get_gl_codes('HOUSE', 'debit'), sums['house']), 
            ('Mobile Allowance', self._get_gl_codes('MOBILE', 'debit'), sums['mobile']), 
            ('Hardship Allowance', self._get_gl_codes('HARDSHIP', 'debit'), sums['hardship']), 
            ('Other Benefits', self._get_gl_codes('OTHER_BEN', 'debit'), sums['other_alw']), 
            ('Overtime', self._get_gl_codes('OT', 'debit'), sums['ot']), 
            ('LOP Adjustment (Credit)', self._get_gl_codes('LOP_ADJ', 'debit'), sums['lop_adj']), 
            ('Pension Payable (Company 11%)', self._get_gl_codes('PENSION_COMP', 'debit'), sums['p_comp']),
            ('Gross Cash Indemnity Allowance', self._get_gl_codes('CASH_IND', 'debit'), sums['ci_gross'])
        ]
        
        d_row = row + 2; d_sum = 0
        for desc, gl, val in debits:
            if round(val, 2) != 0: 
                worksheet.write(d_row, 1, desc, border_fmt)
                worksheet.write(d_row, 2, gl, border_fmt)
                worksheet.write(d_row, 3, val, money_fmt)
                d_sum += val
                d_row += 1
                
        worksheet.merge_range(d_row, 1, d_row, 2, 'TOTAL DEBIT', workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#f2f2f2'}))
        worksheet.write(d_row, 3, d_sum, workbook.add_format({'bold': True, 'border': 1, 'num_format': '#,##0.00', 'bg_color': '#f2f2f2'}))
        
        worksheet.merge_range(row, 6, row, 8, 'Credit Side Analysis', summary_title_fmt)
        worksheet.write(row + 1, 6, 'Description', summary_title_fmt)
        worksheet.write(row + 1, 7, 'GL Code', summary_title_fmt)
        worksheet.write(row + 1, 8, 'Amount', summary_title_fmt)
        
        credits = [
            ('Income Tax', self._get_gl_codes(['TAX', 'CI_TAX'], 'credit'), sums['tax']), 
            ('Pension Payable (18%)', self._get_gl_codes(['PENSION_EMP', 'PENSION_COMP'], 'credit'), sums['p_emp'] + sums['p_comp']), 
            ('Net Salary Payable', self._get_gl_codes('NET', 'credit'), sums['net'] - (sums['ci_to_bal'] + sums['ci_to_sal'])), 
            ('Cost Sharing Payable', self._get_gl_codes('COST_SHARING', 'credit'), sums['c_sharing']), 
            ('Cash Indemnity Staff Account', self._get_gl_codes('CASH_IND', 'credit'), sums['ci_to_bal']), 
            ('Cash Indemnity to Salary Account', self._get_gl_codes('NET', 'credit'), sums['ci_to_sal']), 
            ('Staff Loan Settlement Account (Adv)', self._get_gl_codes('LOAN', 'credit'), sums['adv_loan']), 
            ('Staff Loan Settlement Account (Pers)', self._get_gl_codes('LOAN', 'credit'), sums['pers_loan']), 
            ('Other Loan Repayment', self._get_gl_codes('LOAN', 'credit'), sums['other_loan']), 
            ('Savings Payable', self._get_gl_codes('SAVINGS', 'credit'), sums['savings']), 
            ('Credit Association Payable', self._get_gl_codes('CREDIT_ASSOC', 'credit'), sums['credit_assoc']), 
            ('Penalty Deduction', self._get_gl_codes('PENALTY', 'credit'), sums['penalty']), 
            ('Loss of Pay (LOP)', self._get_gl_codes('LOP_LEAVE', 'credit'), sums['lop_leave']), 
            ('Other Payable Account', self._get_gl_codes('OTHER_DED', 'credit'), sums['other_ded'])
        ]
        
        c_row = row + 2; c_sum = 0
        for desc, gl, val in credits:
            if round(val, 2) != 0: 
                worksheet.write(c_row, 6, desc, border_fmt)
                worksheet.write(c_row, 7, gl, border_fmt)
                worksheet.write(c_row, 8, val, money_fmt)
                c_sum += val
                c_row += 1
                
        worksheet.merge_range(c_row, 6, c_row, 7, 'TOTAL CREDIT', workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#f2f2f2'}))
        worksheet.write(c_row, 8, c_sum, workbook.add_format({'bold': True, 'border': 1, 'num_format': '#,##0.00', 'bg_color': '#f2f2f2'}))

        # --- SHEET 2: PAYMENT TICKETS (CASH INDEMNITY) ---
        worksheet2 = workbook.add_worksheet('Payment Tickets')
        
        # Styles for Tickets
        font_name = 'Times New Roman'
        style_label = workbook.add_format({'bold': True, 'font_size': 11, 'border': 1, 'bg_color': '#bfbfbf', 'align': 'center', 'valign': 'vcenter', 'font_name': font_name}) 
        style_data_box = workbook.add_format({'border': 1, 'font_size': 11, 'align': 'center', 'valign': 'vcenter', 'font_name': font_name, 'bg_color': '#bfbfbf'})
        style_red_label = workbook.add_format({'font_color': 'red', 'bold': True, 'font_size': 10, 'align': 'left', 'font_name': font_name})
        style_bold = workbook.add_format({'bold': True, 'font_name': font_name, 'font_size': 10})
        style_underline = workbook.add_format({'bottom': 1, 'align': 'left', 'font_name': font_name, 'font_size': 11, 'bold': True})
        style_money = workbook.add_format({'font_name': font_name, 'font_size': 11, 'num_format': '#,##0.00', 'align': 'right', 'bold': True})
        
        # Set Columns
        worksheet2.set_column(0, 0, 25)
        worksheet2.set_column(1, 1, 25)
        worksheet2.set_column(2, 2, 2)  # GAP
        worksheet2.set_column(3, 3, 25)
        worksheet2.set_column(4, 4, 25)
        
        # Accounts
        acc_allowance = '5030201' # Debit
        acc_tax = '2020301'       # Credit
        
        t_row = 0
        
        # Internal function to draw ticket
        def draw_ticket(curr_row, title, is_debit, left_header, left_value, right_header, right_value, amount, slip):
            # Fetch branch from employee profile
            branch_name = 'Head Office'
            if slip.employee_id.branch_id:
                branch_name = slip.employee_id.branch_id.name
            
            # Fetch cost center
            cost_center = '999914'
            if slip.contract_id.cost_center_id:
                cost_center = slip.contract_id.cost_center_id.name or slip.contract_id.cost_center_id.code or '999914'

            # Logo
            worksheet2.set_row(curr_row, 60) # ADJUSTED: Set row height to fit logo
            try:
                logo_path = file_path('ahadu_payroll/src/images/Ahadu Bank Logo with Name.jpg')
                if logo_path and os.path.exists(logo_path):
                    worksheet2.insert_image(curr_row, 2, logo_path, {'x_scale': 0.6, 'y_scale': 0.6, 'x_offset': -25})
            except Exception: pass
            
            # Header
            worksheet2.merge_range(curr_row+1, 0, curr_row+1, 4, branch_name, workbook.add_format({'align': 'center', 'bold': True, 'font_color': '#003366', 'font_name': font_name}))
            worksheet2.merge_range(curr_row+2, 0, curr_row+2, 4, title, workbook.add_format({'align': 'center', 'bold': True, 'font_color': '#003366', 'font_name': font_name, 'font_size': 11}))
            
            # Date
            date_str = fields.Date.today().strftime('%d-%b-%y')
            worksheet2.write(curr_row+2, 3, "Date", workbook.add_format({'bold': True, 'align': 'right', 'font_name': font_name}))
            worksheet2.write(curr_row+2, 4, date_str, workbook.add_format({'align': 'center', 'font_name': font_name})) 

            # Labels
            if is_debit:
                worksheet2.write(curr_row+3, 0, f"cost center {cost_center}", style_bold)
                worksheet2.write(curr_row+4, 0, "Debit", style_underline)
                worksheet2.write(curr_row+4, 2, "Contra", style_red_label)
            else:
                worksheet2.write(curr_row+4, 0, "Contra", style_underline)
                worksheet2.write(curr_row+4, 2, "Credit", style_red_label)
                
            # Boxes
            worksheet2.merge_range(curr_row+5, 0, curr_row+5, 1, left_header, style_label)
            worksheet2.merge_range(curr_row+6, 0, curr_row+6, 1, left_value, style_data_box)
            
            worksheet2.merge_range(curr_row+5, 3, curr_row+5, 4, right_header, style_label)
            worksheet2.merge_range(curr_row+6, 3, curr_row+6, 4, right_value, style_data_box)  
            
            # Narrative
            period = f"{batch.date_start.strftime('%B, %d %Y')} Upto {batch.date_end.strftime('%B %d, %Y')}" if batch.date_start else ""
            desc_text = "cash indemnity allowance" if "cash" in left_header.lower() else left_header
            narrative = f"{desc_text} payment to {slip.employee_id.name} for the month of {period}."
            worksheet2.merge_range(curr_row+7, 0, curr_row+8, 4, narrative, workbook.add_format({'text_wrap': True, 'valign': 'top', 'font_name': font_name}))
            
            # Amount
            worksheet2.write(curr_row+9, 0, "Birr", style_bold)
            amount_text = slip.company_id.currency_id.amount_to_text(amount) if slip.company_id.currency_id else str(amount)
            worksheet2.merge_range(curr_row+10, 0, curr_row+10, 2, amount_text, workbook.add_format({'bottom': 1, 'text_wrap': True, 'font_name': font_name, 'font_size': 9}))
            
            worksheet2.write(curr_row+10, 3, "Birr", workbook.add_format({'bold': True, 'align': 'right', 'font_name': font_name}))
            worksheet2.write(curr_row+10, 4, amount, style_money)
            
            # Signature
            worksheet2.merge_range(curr_row+12, 0, curr_row+12, 1, "Prepared By", workbook.add_format({'top': 1, 'bold': True, 'align': 'center', 'font_name': font_name}))
            worksheet2.write(curr_row+12, 2, "Checked By", workbook.add_format({'top': 1, 'bold': True, 'align': 'center', 'font_name': font_name}))
            worksheet2.merge_range(curr_row+12, 3, curr_row+12, 4, "Approved by", workbook.add_format({'top': 1, 'bold': True, 'align': 'center', 'font_name': font_name}))
            
            return curr_row + 14

        # Generate Tickets
        for slip in self._get_payslip_lines(batch):
            if slip.cash_indemnity_allowance > 0:
                emp_name = slip.employee_id.name
                allowance = slip.cash_indemnity_allowance
                tax = slip.cash_indemnity_tax
                net_ci = slip.ci_to_balance
                net_sal = slip.ci_to_salary

                # Bank Accounts
                bank_accounts = request.env['hr.employee.bank.account'].sudo().search([('employee_id', '=', slip.employee_id.id)])
                ci_acc_num = bank_accounts.filtered(lambda a: a.account_type == 'cash_indemnity')[:1].account_number or ''
                sal_acc_num = bank_accounts.filtered(lambda a: a.account_type == 'salary')[:1].account_number or ''
                
                # Ticket 1: Debit Ticket
                t_row = draw_ticket(t_row, "Debit Ticket", True, 
                    "cash indemnity allowance", acc_allowance, 
                    emp_name, f"{ci_acc_num}/{sal_acc_num or 'N/A'}", 
                    allowance, slip)
                
                # Ticket 2: Credit Ticket (Tax)
                t_row = draw_ticket(t_row, "Credit Ticket", False, 
                    "cash indemnity allowance", acc_allowance, 
                    "income tax payable", acc_tax, 
                    tax, slip)

                # Ticket 3: Credit Ticket (Net CI)
                if net_ci > 0:
                     t_row = draw_ticket(t_row, "Credit Ticket", False, 
                        "cash indemnity allowance", acc_allowance, 
                        emp_name, ci_acc_num, 
                        net_ci, slip)
                
                # Ticket 4: Credit Ticket (Net Salary)
                if net_sal > 0:
                     t_row = draw_ticket(t_row, "Credit Ticket", False, 
                        "cash indemnity allowance", acc_allowance, 
                        emp_name, sal_acc_num, 
                        net_sal, slip)
                
                t_row += 1 # Spacer

        workbook.close(); output.seek(0)
        return self._make_excel_response(output, f'Payroll_Sheet_{batch.name}.xlsx')
