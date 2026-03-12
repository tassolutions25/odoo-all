# -*- coding: utf-8 -*-
import io
import logging
from odoo import http
from odoo.http import request
from odoo.tools.misc import xlsxwriter
from .common import AhaduReportCommon

_logger = logging.getLogger(__name__)

class CustomPayrollReport(AhaduReportCommon):

    @http.route('/ahadu_payroll/custom_payroll_report/<int:wizard_id>', type='http', auth='user')
    def download_custom_report(self, wizard_id, **kw):
        wizard = request.env['ahadu.payroll.custom.report'].browse(wizard_id)
        
        # Build Domain
        domain = [
            ('date_from', '>=', wizard.date_from),
            ('date_to', '<=', wizard.date_to),
            ('state', '=', 'done')
        ]
        
        if wizard.pay_group_ids:
            domain.append(('contract_id.pay_group_id', 'in', wizard.pay_group_ids.ids))
        if wizard.branch_ids:
            domain.append(('employee_id.branch_id', 'in', wizard.branch_ids.ids))
        if wizard.department_ids:
            domain.append(('employee_id.department_id', 'in', wizard.department_ids.ids))

        slips = request.env['hr.payslip'].sudo().search(domain, order='employee_id, date_from')
        
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Custom Payroll')
        
        # Styles
        title_fmt = workbook.add_format({'bold': True, 'size': 14, 'align': 'center'})
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
        money_fmt = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
        data_fmt = workbook.add_format({'border': 1})
        
        # Title
        title = f"Custom Payroll Report: {wizard.date_from} to {wizard.date_to}"
        worksheet.merge_range('A1:AK1', title, title_fmt)
        
        # Headers (Reusing patterns from report_payroll_sheet.py)
        headers = [
            'S.N', 'Employee Name', 'Branch/Dept', 'ID No', 'Join Date', 'TIN No',
            'Full Basic', 'Fuel Ltr', 'Fuel Rate', 'Transport', 'Taxable Trans', 'Rep.', 
            'Hardship', 'Housing', 'Mobile', 'CI Gross', 'CI to Bal', 'CI to Sal', 'OT', 
            'Gross Earnings', 'Taxable Income', 'Pension (Co)', 'Tax', 'Pension (Emp)', 
            'Adv. Loan', 'Pers. Loan', 'Other Loan', 'Other Ded', 'Cost Sharing', 'Penalty', 'LOP/Unpaid', 
            'Total Ded', 'Net Pay', 'Salary Acc', 'Adv Loan Acc', 'Pers Loan Acc', 'CI Acc'
        ]
        
        row = 2
        for col, h in enumerate(headers):
            worksheet.write(row, col, h, header_fmt)
            worksheet.set_column(col, col, 15)
        
        row += 1
        seq = 1
        
        # Fuel Rate (Global for period)
        fuel_price_global = float(request.env['ir.config_parameter'].sudo().get_param('ahadu_hr.fuel_price_per_liter', 0.0))

        for slip in slips:
            emp = slip.employee_id
            trans_amt = self._get_rule_total(slip, 'TRANS')
            vals = {
                'full_basic': emp.emp_wage, 
                'basic': self._get_rule_total(slip, 'BASIC'), 
                'trans': trans_amt, 
                'tax_trans': max(0.0, trans_amt - slip._get_region_transport_exemption()), 
                'rep': self._get_rule_total(slip, 'REP'), 
                'house': self._get_rule_total(slip, 'HOUSE'), 
                'hardship': self._get_rule_total(slip, 'HARDSHIP'), 
                'ci_gross': slip.cash_indemnity_allowance,
                'ci_to_bal': slip.ci_to_balance,
                'ci_to_sal': slip.ci_to_salary,
                'mobile': self._get_rule_total(slip, 'MOBILE'), 
                'other_alw': self._get_rule_total(slip, 'OTHER_BEN'), 
                'ot': slip.overtime_amount, 
                'gross': self._get_rule_total(slip, 'GROSS'), 
                't_income': slip._get_ahadu_taxable_gross(), 
                'p_comp': self._get_rule_total(slip, 'PENSION_COMP'), 
                'tax': self._get_rule_total(slip, 'TAX'), 
                'p_emp': self._get_rule_total(slip, 'PENSION_EMP'), 
                'adv_loan': slip._get_ahadu_advance_loan_deduction(), 
                'pers_loan': slip._get_ahadu_personal_loan_deduction(), 
                'other_loan': slip._get_ahadu_other_loan_deduction(), 
                'other_ded': self._get_rule_total(slip, 'OTHER_DED'), 
                'c_sharing': self._get_rule_total(slip, 'COST_SHARING'),
                'penalty': abs(self._get_rule_total(slip, 'PENALTY')), 
                'lop_leave': self._get_rule_total(slip, 'LOP_LEAVE'), 
                'total_ded': sum(slip.line_ids.filtered(lambda r: r.category_id.code == 'DED').mapped('total')), 
                'net': self._get_rule_total(slip, 'NET')
            }

            worksheet.write(row, 0, seq, data_fmt)
            worksheet.write(row, 1, emp.name, data_fmt)
            
            # Dept/Branch logic: Head Office -> Show Department
            branch_name = emp.branch_id.name or ""
            if branch_name.lower() == 'head office':
                dept_branch = emp.department_id.name or branch_name
            else:
                dept_branch = branch_name or (emp.department_id.name or "")

            worksheet.write(row, 2, dept_branch, data_fmt)
            worksheet.write(row, 3, emp.employee_id or '', data_fmt)
            worksheet.write(row, 4, str(slip.contract_id.date_start) if slip.contract_id.date_start else '', data_fmt)
            worksheet.write(row, 5, emp.tin_number or '', data_fmt)
            
            worksheet.write(row, 6, vals['full_basic'], money_fmt)
            worksheet.write(row, 7, emp.transport_allowance_liters, data_fmt)
            worksheet.write(row, 8, fuel_price_global, money_fmt)
            worksheet.write(row, 9, vals['trans'], money_fmt)
            worksheet.write(row, 10, vals['tax_trans'], money_fmt)
            worksheet.write(row, 11, vals['rep'], money_fmt)
            worksheet.write(row, 12, vals['hardship'], money_fmt)
            worksheet.write(row, 13, vals['house'], money_fmt)
            worksheet.write(row, 14, vals['mobile'], money_fmt)
            worksheet.write(row, 15, vals['ci_gross'], money_fmt)
            worksheet.write(row, 16, vals['ci_to_bal'], money_fmt)
            worksheet.write(row, 17, vals['ci_to_sal'], money_fmt)
            worksheet.write(row, 18, vals['ot'], money_fmt)
            worksheet.write(row, 19, vals['gross'], money_fmt)
            worksheet.write(row, 20, vals['t_income'], money_fmt)
            worksheet.write(row, 21, vals['p_comp'], money_fmt)
            worksheet.write(row, 22, vals['tax'], money_fmt)
            worksheet.write(row, 23, vals['p_emp'], money_fmt)
            worksheet.write(row, 24, vals['adv_loan'], money_fmt)
            worksheet.write(row, 25, vals['pers_loan'], money_fmt)
            worksheet.write(row, 26, vals['other_loan'], money_fmt)
            worksheet.write(row, 27, vals['other_ded'], money_fmt)
            worksheet.write(row, 28, vals['c_sharing'], money_fmt)
            worksheet.write(row, 29, vals['penalty'], money_fmt)
            worksheet.write(row, 30, vals['lop_leave'], money_fmt)
            worksheet.write(row, 31, vals['total_ded'], money_fmt)
            worksheet.write(row, 32, vals['net'], money_fmt)
            
            # Accounts
            bank_accounts = request.env['hr.employee.bank.account'].sudo().search([('employee_id', '=', slip.employee_id.id)])
            salary_acc = bank_accounts.filtered(lambda a: a.account_type == 'salary')[:1].account_number or ''
            ci_acc = bank_accounts.filtered(lambda a: a.account_type == 'cash_indemnity')[:1].account_number or ''
            
            # Loan account(s)
            active_loans_adv = request.env['hr.loan'].sudo().search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'approved'),
                ('date_start', '<=', slip.date_to),
                ('loan_type_id.name', '=', 'Emergency/Salary Advance Loan')
            ])
            active_loans_pers = request.env['hr.loan'].sudo().search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'approved'),
                ('date_start', '<=', slip.date_to),
                ('loan_type_id.name', '=', 'Personal Staff Loan')
            ])
            
            adv_loan_acc = active_loans_adv[0].bank_account_id.account_number if active_loans_adv and active_loans_adv[0].bank_account_id else ''
            pers_loan_acc = active_loans_pers[0].bank_account_id.account_number if active_loans_pers and active_loans_pers[0].bank_account_id else ''

            worksheet.write(row, 33, salary_acc, data_fmt)
            worksheet.write(row, 34, adv_loan_acc, data_fmt)
            worksheet.write(row, 35, pers_loan_acc, data_fmt)
            worksheet.write(row, 36, ci_acc, data_fmt)
            
            row += 1
            seq += 1

        workbook.close()
        output.seek(0)
        return request.make_response(output.getvalue(), headers=[
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', f'attachment; filename="Custom_Payroll_Report_{wizard.date_from}_{wizard.date_to}.xlsx"')
        ])
