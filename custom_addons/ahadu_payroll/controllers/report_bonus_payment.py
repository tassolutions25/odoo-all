# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import io
import xlsxwriter
import datetime
from num2words import num2words
from collections import defaultdict

class BonusPaymentExcelReportController(http.Controller):

    @http.route('/ahadu_payroll/bonus_excel/<int:bonus_id>', type='http', auth='user')
    def download_bonus_excel(self, bonus_id, **kw):
        bonus = request.env['ahadu.bonus.payment'].browse(bonus_id)
        if not bonus.exists():
            return request.not_found()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        
        # Formats
        title_format = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_size': 12})
        header_format = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'border': 1, 'bg_color': '#D9D9D9', 'text_wrap': True
        })
        cell_format = workbook.add_format({'border': 1, 'align': 'left', 'valign': 'vcenter'})
        num_format = workbook.add_format({'border': 1, 'align': 'right', 'valign': 'vcenter', 'num_format': '#,##0.00'})
        date_format = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'num_format': 'dd-mmm-yy'})
        
        # Ticket Formats
        ticket_header_format = workbook.add_format({'bold': True, 'font_size': 12})
        ticket_table_header = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#F2F2F2', 'align': 'center'})
        ticket_cell_border = workbook.add_format({'border': 1})
        ticket_cell_border_right = workbook.add_format({'border': 1, 'align': 'right', 'num_format': '#,##0.00'})
        
        # -------------------------------------------------------------
        # SHEET 1: Detailed List
        # -------------------------------------------------------------
        sheet_name = f"Bonus {bonus.date.strftime('%b %Y')}" if bonus.date else 'Bonus List'
        sheet1 = workbook.add_worksheet(sheet_name[:31])
        
        # Merge top headers
        sheet1.merge_range('A1:U1', 'Finance and treasury department', title_format)
        sheet1.merge_range('A2:U2', bonus.name or 'Bonus Payment', title_format)
        
        # Headers Row 3 (Categories)
        sheet1.write('A3', 'S.No', header_format)
        sheet1.merge_range('B3:G3', 'Employees Basic Information', header_format)
        sheet1.merge_range('H3:N3', 'Bonus Entitlement & Period of Service', header_format)
        sheet1.merge_range('O3:S3', 'Tax Workout', header_format)
        sheet1.merge_range('T3:V3', 'Payment to be made', header_format)
        
        # Headers Row 4 (Columns)
        headers = [
            'S.No', 'Salary Account Number', 'Tin Number', 'ID No', 'Employee Full Name', 
            'Job Title', 'Employement Date', 'Monthly Salary', 'Period End Date', 
            'Total Working Months', 'Department /Branch', f'Months {bonus.date.year}', 
            'Bonus Entitlement', 'Bonus Per Month', 'Salary Paid', 
            'Tax - A', 'Salary Plus Bonus', 'Tax - B', 'Tax - Difference', 
            'Bonus Amount', 'Bonus Tax', 'Net Bonus Pay'
        ]
        
        for col_num, header in enumerate(headers):
            sheet1.write(3, col_num, header, header_format)
            
        # Set column widths
        sheet1.set_column('B:E', 20)
        sheet1.set_column('F:I', 15)
        sheet1.set_column('J:J', 10)
        sheet1.set_column('K:K', 25)
        sheet1.set_column('L:V', 15)
        
        # Data Rows
        row = 4
        s_no = 1
        
        # Prepare groupings for Sheet 2
        groups = defaultdict(lambda: {'amount': 0.0, 'cost_center': ''})
        total_tax = 0.0
        total_net = 0.0
        
        for line in bonus.line_ids:
            dept = line.department_id.name or 'Unknown Department'
            cc = line.department_id.cost_center_id.code if line.department_id and line.department_id.cost_center_id else 'N/A'
            is_mgr = line.is_managerial
            
            group_key = f"{dept}|{is_mgr}|{cc}"
            groups[group_key]['amount'] += line.bonus_amount
            groups[group_key]['cost_center'] = cc
            
            total_tax += line.bonus_tax
            total_net += line.net_bonus_pay
            
            sheet1.write(row, 0, s_no, cell_format)
            sheet1.write(row, 1, line.salary_account_number or '', cell_format)
            sheet1.write(row, 2, line.tin_number or '', cell_format)
            sheet1.write(row, 3, line.employee_id_no or '', cell_format)
            sheet1.write(row, 4, line.employee_id.name or '', cell_format)
            sheet1.write(row, 5, line.job_id.name if line.job_id else '', cell_format)
            
            if line.employment_date:
                sheet1.write_datetime(row, 6, line.employment_date, date_format)
            else:
                sheet1.write(row, 6, '', cell_format)
                
            sheet1.write(row, 7, line.monthly_salary, num_format)
            
            if bonus.cutoff_date:
                sheet1.write_datetime(row, 8, bonus.cutoff_date, date_format)
            else:
                sheet1.write(row, 8, '', cell_format)
                
            sheet1.write(row, 9, line.total_working_months, num_format)
            sheet1.write(row, 10, dept, cell_format)
            sheet1.write(row, 11, bonus.months_of_year, cell_format)
            sheet1.write(row, 12, line.bonus_entitlement, num_format)
            sheet1.write(row, 13, line.bonus_per_month, num_format)
            sheet1.write(row, 14, line.salary_paid_during_mid, num_format)
            sheet1.write(row, 15, line.tax_a, num_format)
            sheet1.write(row, 16, line.salary_plus_bonus, num_format)
            sheet1.write(row, 17, line.tax_b, num_format)
            sheet1.write(row, 18, line.tax_difference, num_format)
            sheet1.write(row, 19, line.bonus_amount, num_format)
            sheet1.write(row, 20, line.bonus_tax, num_format)
            sheet1.write(row, 21, line.net_bonus_pay, num_format)
            
            row += 1
            s_no += 1
            
        # Grand Totals
        sheet1.write(row, 10, 'GRAND TOTAL', header_format)
        sheet1.write(row, 12, sum(bonus.line_ids.mapped('bonus_entitlement')), num_format)
        sheet1.write(row, 13, sum(bonus.line_ids.mapped('bonus_per_month')), num_format)
        sheet1.write(row, 14, sum(bonus.line_ids.mapped('salary_paid_during_mid')), num_format)
        sheet1.write(row, 15, sum(bonus.line_ids.mapped('tax_a')), num_format)
        sheet1.write(row, 16, sum(bonus.line_ids.mapped('salary_plus_bonus')), num_format)
        sheet1.write(row, 17, sum(bonus.line_ids.mapped('tax_b')), num_format)
        sheet1.write(row, 18, sum(bonus.line_ids.mapped('tax_difference')), num_format)
        sheet1.write(row, 19, sum(bonus.line_ids.mapped('bonus_amount')), num_format)
        sheet1.write(row, 20, sum(bonus.line_ids.mapped('bonus_tax')), num_format)
        sheet1.write(row, 21, sum(bonus.line_ids.mapped('net_bonus_pay')), num_format)
        
        # -------------------------------------------------------------
        # SHEET 2: Tickets
        # -------------------------------------------------------------
        sheet2 = workbook.add_worksheet('Bonus Ticket')
        sheet2.set_column('A:A', 5)
        sheet2.set_column('B:E', 20)
        sheet2.set_column('F:H', 15)
        
        t_row = 1
        
        def write_ticket(sheet, start_row, cost_center, title, debit_gl, debit_desc, contra_gl, contra_desc, amount, memo, is_debit=True):
            # Render a single ticket box
            amt_words = num2words(amount).replace(',', '').lower() + " birr & 00/100."
            date_str = bonus.date.strftime('%d-%b-%y') if bonus.date else ''
            
            # Header
            sheet.write(start_row, 3, 'Head office', ticket_header_format)
            sheet.write(start_row, 5, 'Date:', ticket_header_format)
            sheet.write(start_row, 6, date_str)
            
            sheet.write(start_row + 1, 1, f'COST center {cost_center}', ticket_header_format)
            sheet.write(start_row + 1, 3, title, ticket_header_format)
            
            # Labels
            if is_debit:
                sheet.write(start_row + 2, 1, 'Debit', ticket_header_format)
                sheet.write(start_row + 2, 5, 'Contra', ticket_header_format)
            else:
                sheet.write(start_row + 2, 1, 'Contra', ticket_header_format)
                sheet.write(start_row + 2, 5, 'Credit', ticket_header_format)
                
            # Table Header
            sheet.write(start_row + 4, 1, debit_desc, ticket_table_header)
            sheet.write(start_row + 4, 2, '', ticket_table_header)
            sheet.write(start_row + 4, 3, '', ticket_table_header)
            sheet.write(start_row + 4, 4, '', ticket_table_header)
            sheet.write(start_row + 4, 5, contra_desc, ticket_table_header)
            sheet.write(start_row + 4, 6, '', ticket_table_header)
            
            sheet.write(start_row + 5, 1, debit_gl, ticket_cell_border)
            sheet.write(start_row + 5, 5, contra_gl, ticket_cell_border)
            
            # Memo
            sheet.write(start_row + 7, 1, memo)
            
            # Amount Words
            sheet.write(start_row + 9, 1, 'Birr')
            sheet.write(start_row + 9, 2, amt_words)
            
            # Amount Value
            sheet.write(start_row + 10, 4, 'Birr', ticket_header_format)
            sheet.write(start_row + 10, 5, amount, ticket_cell_border_right)
            
            # Signatures
            sheet.write(start_row + 13, 1, '_____________')
            sheet.write(start_row + 13, 3, '________________')
            sheet.write(start_row + 13, 5, '_____________________')
            
            sheet.write(start_row + 14, 1, 'Prepared By')
            sheet.write(start_row + 14, 3, 'Checked By')
            sheet.write(start_row + 14, 5, 'Approved by')
            
            return start_row + 18
            
        # Draw Debit Tickets
        for group_key, data in groups.items():
            if data['amount'] <= 0:
                continue
            dept, is_mgr_str, cc = group_key.split('|')
            is_mgr = is_mgr_str == 'True'
            
            gl_account = '5030106' if is_mgr else '5030107'
            level_str = 'managerial' if is_mgr else 'Non managerial'
            
            memo = f"bonus payment to {level_str} {dept.lower()} staffs for {bonus.period_type} year or \nhere attached approval bonus payment of memo."
            
            t_row = write_ticket(
                sheet2, t_row, cc, 'Debit Ticket', 
                f"Bonus-{level_str.capitalize()} Staff", "Varius Gl & accounts",
                gl_account, "", data['amount'], memo, True
            )
            
        # Draw Credit Tickets (Tax & Net Pay)
        
        # 1. Tax
        if total_tax > 0:
            memo_tax = "employee income tax collected from various department staffs"
            t_row = write_ticket(
                sheet2, t_row, 'HeadOffice', 'Credit Ticket',
                "bones managerial & non managerial pososition", "employee income tax",
                "5030106 & 5030107 respectivly", "2020301",
                total_tax, memo_tax, False
            )
            
        # 2. Net Pay
        if total_net > 0:
            memo_net = "net bones payment for all staffs"
            write_ticket(
                sheet2, t_row, 'HeadOffice', 'Credit Ticket',
                "bones managerial & non managerial pososition", "various staff Accounts",
                "5030106 & 5030107 respectivly", "",
                total_net, memo_net, False
            )

        workbook.close()
        output.seek(0)

        file_name = f'Bonus_Payment_{bonus.id}.xlsx'
        headers = [
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', f'attachment; filename={file_name}')
        ]
        
        return request.make_response(output.read(), headers=headers)
