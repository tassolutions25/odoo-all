# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import io
import xlsxwriter
from datetime import datetime

class BackpayExcelReportController(http.Controller):

    @http.route('/ahadu_payroll/backpay_excel/<int:batch_id>', type='http', auth='user')
    def download_backpay_excel(self, batch_id, **kw):
        batch = request.env['ahadu.backpay.batch'].browse(batch_id)
        if not batch.exists():
            return request.not_found()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        
        # Formats
        title_format = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_size': 14})
        subtitle_format = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_size': 11})
        header_format = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'border': 1, 'bg_color': '#D9D9D9', 'text_wrap': True, 'font_size': 9
        })
        cell_format = workbook.add_format({'border': 1, 'align': 'left', 'valign': 'vcenter', 'font_size': 9})
        num_format = workbook.add_format({'border': 1, 'align': 'right', 'valign': 'vcenter', 'num_format': '#,##0.00', 'font_size': 9})
        diff_num_format = workbook.add_format({'border': 1, 'align': 'right', 'valign': 'vcenter', 'num_format': '#,##0.00', 'font_size': 9, 'bold': True})
        date_format = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'num_format': 'dd/mm/yyyy', 'font_size': 9})
        
        sheet_name = f"Backpay_{batch.month}_{batch.year}"
        sheet = workbook.add_worksheet(sheet_name[:31])
        
        # Header setup (matching the user's provided template)
        # BACK PAYMENT OF SALARY FOR CLERICAL STAFFS
        # FOR THE MONTH OF July 31, 2023
        month_label = dict(batch._fields['month'].selection).get(batch.month)
        title = "BACK PAYMENT OF SALARY FOR CLERICAL STAFFS"
        subtitle = f"FOR THE MONTH OF {month_label} {batch.year}"
        
        sheet.merge_range('A1:U1', title, title_format)
        sheet.merge_range('A2:U2', subtitle, subtitle_format)
        
        # Table Headers
        headers = [
            'S.N', 'Name of Employee', 'Date of Employees', 'Effective Date', 'Basic salary', 'Litre', 'Fuel rate', 
            'Transport Allowance', 'Taxable Transport Allowance', 'Representation', 
            'Housing Allowance', 'Mobile Allowance', 'OT', 'Gross Salary & Benefits', 
            'Taxable Salary & Benefits', 'Pension 11%', 'Income Tax', 'Pension 7%', 
            'Other Deductions', 'Total Deduction', 'Net Income', 'BANK ACCOUNT'
        ]
        
        for col_num, header in enumerate(headers):
            sheet.write(3, col_num, header, header_format)
            
        # Column widths
        sheet.set_column('A:A', 5)
        sheet.set_column('B:B', 30)
        sheet.set_column('C:D', 15)
        sheet.set_column('E:V', 12)
        
        row = 4
        s_no = 1
        
        for line in batch.line_ids:
            # Row 1: Old Values
            sheet.write(row, 0, s_no, cell_format)
            sheet.write(row, 1, line.employee_id.name, cell_format)
            if line.joining_date:
                sheet.write_datetime(row, 2, line.joining_date, date_format)
            else:
                sheet.write(row, 2, '', cell_format)
            
            sheet.write(row, 3, '', cell_format) # Effective date not for old row context usually
            
            sheet.write(row, 4, line.old_basic, num_format)
            sheet.write(row, 5, line.old_fuel_liters, num_format)
            sheet.write(row, 6, line.old_fuel_rate, num_format)
            sheet.write(row, 7, line.old_transport, num_format)
            sheet.write(row, 8, line.old_taxable_transport, num_format)
            sheet.write(row, 9, line.old_representation, num_format)
            sheet.write(row, 10, line.old_housing, num_format)
            sheet.write(row, 11, line.old_mobile, num_format)
            sheet.write(row, 12, line.old_ot, num_format)
            sheet.write(row, 13, line.old_gross, num_format)
            sheet.write(row, 14, line.old_taxable_gross, num_format)
            sheet.write(row, 15, line.old_pension_comp, num_format)
            sheet.write(row, 16, line.old_income_tax, num_format)
            sheet.write(row, 17, line.old_pension_emp, num_format)
            sheet.write(row, 18, line.old_other_deductions, num_format)
            sheet.write(row, 19, line.old_total_deductions, num_format)
            sheet.write(row, 20, line.old_net, num_format)
            sheet.write(row, 21, line.bank_account or '', cell_format)
            
            row += 1
            
            # Row 2: New Values
            sheet.write(row, 0, s_no, cell_format)
            sheet.write(row, 1, line.employee_id.name, cell_format)
            if line.joining_date:
                sheet.write_datetime(row, 2, line.joining_date, date_format)
            else:
                sheet.write(row, 2, '', cell_format)
            
            if line.effective_date:
                sheet.write_datetime(row, 3, line.effective_date, date_format)
            else:
                sheet.write(row, 3, '', cell_format)
            
            sheet.write(row, 4, line.new_basic, num_format)
            sheet.write(row, 5, line.new_fuel_liters, num_format)
            sheet.write(row, 6, line.new_fuel_rate, num_format)
            sheet.write(row, 7, line.new_transport, num_format)
            sheet.write(row, 8, line.new_taxable_transport, num_format)
            sheet.write(row, 9, line.new_representation, num_format)
            sheet.write(row, 10, line.new_housing, num_format)
            sheet.write(row, 11, line.new_mobile, num_format)
            sheet.write(row, 12, line.new_ot, num_format)
            sheet.write(row, 13, line.new_gross, num_format)
            sheet.write(row, 14, line.new_taxable_gross, num_format)
            sheet.write(row, 15, line.new_pension_comp, num_format)
            sheet.write(row, 16, line.new_income_tax, num_format)
            sheet.write(row, 17, line.new_pension_emp, num_format)
            sheet.write(row, 18, line.new_other_deductions, num_format)
            sheet.write(row, 19, line.new_total_deductions, num_format)
            sheet.write(row, 20, line.new_net, num_format)
            sheet.write(row, 21, line.bank_account or '', cell_format)
            
            row += 1
            
            # Row 3: Difference
            sheet.write(row, 0, '', cell_format)
            sheet.write(row, 1, '', cell_format)
            sheet.write(row, 2, '', cell_format)
            
            sheet.write(row, 3, '', cell_format)
            
            sheet.write(row, 4, line.new_basic - line.old_basic, diff_num_format)
            sheet.write(row, 5, line.new_fuel_liters - line.old_fuel_liters, diff_num_format)
            sheet.write(row, 6, '', diff_num_format) # rate diff not needed usually
            sheet.write(row, 7, line.new_transport - line.old_transport, diff_num_format)
            sheet.write(row, 8, line.new_taxable_transport - line.old_taxable_transport, diff_num_format)
            sheet.write(row, 9, line.new_representation - line.old_representation, diff_num_format)
            sheet.write(row, 10, line.new_housing - line.old_housing, diff_num_format)
            sheet.write(row, 11, line.new_mobile - line.old_mobile, diff_num_format)
            sheet.write(row, 12, line.new_ot - line.old_ot, diff_num_format)
            sheet.write(row, 13, line.new_gross - line.old_gross, diff_num_format)
            sheet.write(row, 14, line.new_taxable_gross - line.old_taxable_gross, diff_num_format)
            sheet.write(row, 15, line.new_pension_comp - line.old_pension_comp, diff_num_format)
            sheet.write(row, 16, line.new_income_tax - line.old_income_tax, diff_num_format)
            sheet.write(row, 17, line.new_pension_emp - line.old_pension_emp, diff_num_format)
            sheet.write(row, 18, line.new_other_deductions - line.old_other_deductions, diff_num_format)
            sheet.write(row, 19, line.new_total_deductions - line.old_total_deductions, diff_num_format)
            sheet.write(row, 20, line.new_net - line.old_net, diff_num_format)
            sheet.write(row, 21, line.bank_account or '', cell_format)
            
            row += 1
            s_no += 1

        workbook.close()
        output.seek(0)
        
        file_name = f'Backpay_{batch.month}_{batch.year}.xlsx'
        headers = [
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', f'attachment; filename={file_name}')
        ]
        
        return request.make_response(output.read(), headers=headers)
