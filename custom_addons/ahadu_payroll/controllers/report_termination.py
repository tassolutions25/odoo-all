# -*- coding: utf-8 -*-
import io
import os
import logging
from odoo import http
from odoo.http import request
from odoo.tools.misc import xlsxwriter
from odoo.modules.module import get_module_resource
from .common import AhaduReportCommon

_logger = logging.getLogger(__name__)

class TerminationReport(AhaduReportCommon):
    
    @http.route('/ahadu_payroll/termination_excel/<int:run_id>', type='http', auth='user')
    def download_termination_excel(self, run_id, **kw):
        run = request.env['hr.termination.run'].browse(run_id)
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        # --- Styles ---
        font_header = 'Calibri'
        
        # Title Formats
        title_fmt = workbook.add_format({'bold': True, 'size': 16, 'align': 'center', 'valign': 'vcenter', 'font_color': '#840036', 'font_name': font_header})
        subtitle_fmt = workbook.add_format({'bold': True, 'size': 12, 'align': 'center', 'valign': 'vcenter', 'font_name': font_header})
        
        # Section Headers
        section_header_fmt = workbook.add_format({'bold': True, 'size': 11, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#ffffff', 'font_name': font_header})
        
        # Data Labels
        label_fmt = workbook.add_format({'font_size': 11, 'valign': 'vcenter', 'font_name': font_header})
        label_bold_fmt = workbook.add_format({'bold': True, 'font_size': 11, 'valign': 'vcenter', 'font_name': font_header})
        
        # Values
        money_fmt = workbook.add_format({'num_format': '#,##0.00', 'font_size': 11, 'valign': 'vcenter', 'font_name': font_header})
        money_bold_fmt = workbook.add_format({'num_format': '#,##0.00', 'bold': True, 'font_size': 11, 'valign': 'vcenter', 'font_name': font_header})
        
        # Highlighted Values (Yellow background)
        yellow_money_fmt = workbook.add_format({'num_format': '#,##0.00', 'bold': True, 'font_size': 11, 'valign': 'vcenter', 'bg_color': '#FFFF00', 'font_name': font_header, 'italic': True})
        
        # Header Box for Days
        box_fmt = workbook.add_format({'border': 1, 'align': 'center', 'bold': True, 'font_size': 11})

        # --- Helper to add image ---
        def add_logo(sheet):
            try:
                image_path = get_module_resource('ahadu_payroll', 'src', 'images', 'Ahadu Bank Logo with Name.jpg')
                if image_path and os.path.exists(image_path):
                    sheet.insert_image('C1', image_path, {'x_scale': 0.8, 'y_scale': 0.8, 'x_offset': 15})
                else:
                    sheet.merge_range('A1:G1', "Ahadu Bank S.C", title_fmt)
            except:
                sheet.merge_range('A1:G1', "Ahadu Bank S.C", title_fmt)
        
        # --- Generate Sheet per Employee ---
        for slip in run.slip_ids:
            # Sheet Name (Cleaned)
            sheet_name = slip.employee_id.name[:30].replace(':', '').replace('/', '')
            worksheet = workbook.add_worksheet(sheet_name)
            
            # Columns Width
            worksheet.set_column(0, 0, 35) # Labels
            worksheet.set_column(1, 2, 5)  # Spacers
            worksheet.set_column(3, 3, 10) # Day Box
            worksheet.set_column(4, 4, 15) # Values Right
            worksheet.set_column(5, 5, 20) # Comments
            
            # 1. Header
            add_logo(worksheet)
            
            row = 4
            # Title
            title_text = f"Termination Payment For {slip.employee_id.name} @{slip.employee_id.department_id.name or 'Unknown Dept'} staff"
            worksheet.merge_range(row, 0, row, 5, title_text, subtitle_fmt)
            row += 1
            
            # --- SECTION 1: UNUTILIZED LEAVE PAYMENT ---
            worksheet.merge_range(row, 0, row, 5, "Unutilized Leave Payment", section_header_fmt)
            row += 1
            
            # Day Box Row
            worksheet.write(row, 3, slip.leave_days, box_fmt)
            worksheet.write(row, 4, "Day", label_bold_fmt)
            row += 1
            
            # Basic wage top reference
            worksheet.write(row, 4, slip.wage, money_bold_fmt)
            row += 1
            
            # Basic Salary
            worksheet.write(row, 0, "Basic Salary", label_fmt)
            worksheet.write(row, 4, slip.wage, money_fmt)
            row += 1
            
            # Leave pay for X working days
            worksheet.write(row, 0, f"Leave pay for {slip.leave_days} working days", label_fmt)
            worksheet.write(row, 4, slip.leave_pay_gross, money_fmt)
            row += 1
            
            # Leave Pay For Each Months
            worksheet.write(row, 0, "Leave Pay For Each Months", label_fmt)
            val_per_month = slip.leave_pay_gross / 12.0
            worksheet.write(row, 4, val_per_month, money_fmt)
            row += 1
            
            # Tax Included Annual Leave
            worksheet.write(row, 0, "Tax Included Annual Leave", label_fmt)
            worksheet.write(row, 4, slip.wage + val_per_month, money_fmt)
            row += 1
            
            # Less: Tax (First Highlight)
            # Need access to tax calc. Since I can't easily call private method on recordset if strictly private,
            # but in Odoo `_calculate_tax_old` is likely public enough for python.
            # If not, I should have exposed it. Assuming it works as per previous main.py logic.
            # Original code: tax_1 = run.slip_ids._calculate_tax_old(slip.wage + val_per_month)
            # But `run.slip_ids` is a recordset of multiple. calling method on it works? 
            # It should be called on model or sigle record.
            # In main.py I saw: `tax_1 = run.slip_ids._calculate_tax_old(slip.wage + val_per_month)`
            # This looks risky if slip_ids is empty or has multiple.
            # Better to call on `slip`.
            tax_1 = slip._calculate_tax_old(slip.wage + val_per_month)
            worksheet.write(row, 0, "Less: Tax", label_fmt)
            worksheet.write(row, 4, f"({tax_1:,.2f})", yellow_money_fmt) 
            row += 1
            
            # Tax Excluded Annual Tax
            worksheet.write(row, 0, "Tax Excluded Annual Tax", label_fmt)
            worksheet.write(row, 4, slip.wage, money_fmt)
            row += 1
            
            # Less: Tax (Second Highlight)
            tax_2 = slip._calculate_tax_new(slip.wage)
            worksheet.write(row, 0, "Less: Tax", label_bold_fmt) 
            worksheet.write(row, 3, "Less: Tax", label_bold_fmt) 
            worksheet.write(row, 4, f"({tax_2:,.2f})", yellow_money_fmt)
            row += 1
            
            # Tax Difference
            worksheet.write(row, 0, "Tax Difference", label_bold_fmt) 
            diff = tax_1 - tax_2
            worksheet.write(row, 5, f"({diff:,.2f})", money_fmt) 
            row += 1
            
            # Tax To Paid for Leave
            worksheet.write(row, 0, "Tax To Paid for Leave", label_bold_fmt) 
            worksheet.write(row, 4, f"({slip.leave_pay_tax:,.2f})", money_bold_fmt)
            row += 1
            
            # --- SECTION 2: SALARY AND BENEFIT ---
            worksheet.merge_range(row, 0, row, 5, f"Salary and Benefit {slip.present_days} Days", section_header_fmt)
            row += 1
            
            # Unpaid Salary
            worksheet.write(row, 0, "Unpaid Salary", label_fmt)
            worksheet.write(row, 4, slip.unpaid_salary, money_fmt)
            row += 1
            
            # Unpaid Transport Allowance
            worksheet.write(row, 0, "Unpaid Transport allowance", label_fmt)
            worksheet.write(row, 4, slip.unpaid_transport, money_fmt)
            row += 1
            
            # Representation Allowance
            worksheet.write(row, 0, "Representation Allowance", label_fmt)
            worksheet.write(row, 4, slip.representation_allowance, money_fmt)
            row += 1
            
            # Unpaid Housing Allowance
            worksheet.write(row, 0, "Unpaid Housing allowance", label_fmt)
            worksheet.write(row, 4, slip.unpaid_housing, money_fmt)
            row += 1
            
            # Unpaid Mobile Allowance
            worksheet.write(row, 0, "Unpaid Mobile allowance", label_fmt)
            worksheet.write(row, 4, slip.unpaid_mobile, money_fmt)
            row += 1
            
            # Gross Amount
            worksheet.write(row, 0, "Gross amount", label_bold_fmt)
            worksheet.write(row, 4, slip.gross_amount, money_bold_fmt)
            row += 1
            
            # Taxable Amount
            worksheet.write(row, 0, "Taxable amount", label_bold_fmt)
            worksheet.write(row, 4, slip.taxable_amount, money_bold_fmt)
            row += 1
            
            # Less: Tax (Salary)
            worksheet.write(row, 0, "Less: Tax", label_bold_fmt)
            worksheet.write(row, 4, f"({slip.tax_salary:,.2f})", yellow_money_fmt)
            row += 1
            
            # --- SECTION 3: DEDUCTION ---
            worksheet.merge_range(row, 0, row, 5, "Deduction:", workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'font_name': font_header}))
            row += 1
            
            # Grand Tax Amounts to be paid
            worksheet.write(row, 0, "Grand Tax Amounts to be paid", label_fmt)
            worksheet.write(row, 4, f"({slip.grand_tax:,.2f})", money_fmt)
            row += 1
            
            # Deduction Pension of employee(7%)
            worksheet.write(row, 0, "Deduction Pension of employee(7%)", label_fmt)
            worksheet.write(row, 4, f"({slip.pension_emp:,.2f})", money_fmt)
            row += 1
            
            # Total Deduction
            sub_deduction = slip.grand_tax + slip.pension_emp
            worksheet.write(row, 0, "Total Deduction", label_bold_fmt)
            worksheet.write(row, 4, f"({sub_deduction:,.2f})", money_bold_fmt)
            row += 1
            
            # Pension contribution of employer(11%)
            worksheet.write(row, 0, "Pension contribution of employer(11%)", label_fmt)
            worksheet.write(row, 5, slip.pension_comp, money_bold_fmt)
            row += 1
            
            # Lost of ID card
            worksheet.write(row, 0, "Lost of ID card deducted from the above staff", label_fmt)
            val_lost_id = slip.lost_id_card
            worksheet.write(row, 5, val_lost_id if val_lost_id else '-', money_fmt)
            row += 1
            
            # 15% VAT
            worksheet.write(row, 0, "15% of value added tax deducted from the above staff", label_fmt)
            val_vat = slip.vat_on_id_card
            worksheet.write(row, 5, val_vat if val_vat else '-', money_fmt)
            row += 1
            
            # --- NET PAYABLE ---
            worksheet.merge_range(row, 0, row, 5, "", workbook.add_format({'bg_color': '#bfbfbf'})) # Grey bar
            worksheet.write(row, 0, "Net termination Payable", workbook.add_format({'bold': True, 'bg_color': '#bfbfbf', 'font_name': font_header}))
            worksheet.write(row, 5, slip.net_payable, workbook.add_format({'bold': True, 'num_format': '#,##0.00', 'bg_color': '#bfbfbf', 'font_name': font_header}))
            row += 2
            
            # --- FOOTER ---
            worksheet.write(row, 3, "Name of Staff", label_bold_fmt)
            worksheet.write(row, 5, slip.employee_id.name, label_fmt)
            row += 1
            
            acc = request.env['hr.employee.bank.account'].sudo().search([
                     ('employee_id', '=', slip.employee_id.id),
                     ('account_type', '=', 'salary')
                 ], limit=1)
            acc_num = acc.account_number if acc else "N/A"
            
            worksheet.write(row, 3, "credit account number", workbook.add_format({'font_color': 'blue', 'underline': True, 'font_name': font_header}))
            worksheet.write(row, 5, acc_num, label_fmt)
            row += 1
            
            worksheet.write(row, 3, "TIN", label_bold_fmt)
            worksheet.write(row, 5, slip.employee_id.tin_number or '', label_bold_fmt)
            row += 3
            
            # Signatures
            worksheet.write(row, 0, "Prepared by:", label_bold_fmt)
            worksheet.write(row, 3, "Checked By:", label_bold_fmt)
            worksheet.write(row, 5, "Approved by:", label_bold_fmt)
            row += 2
             
            dots = "."*30
            worksheet.write(row, 0, dots, label_fmt)
            worksheet.write(row, 3, dots, label_fmt)
            worksheet.write(row, 5, dots, label_fmt)

        # --- LAST SHEET: BANK TRANSFER ---
        sheet_bank = workbook.add_worksheet('Bank Transfer')
        sheet_bank.set_column(0, 0, 25) # Account
        sheet_bank.set_column(1, 1, 35) # Name
        sheet_bank.set_column(2, 2, 15) # Amount
        
        # Headers
        sheet_bank.write(0, 0, "Account Number", label_bold_fmt)
        sheet_bank.write(0, 1, "Account Name", label_bold_fmt)
        sheet_bank.write(0, 2, "Amount", label_bold_fmt)
        
        row = 1
        total_transfer = 0.0
        
        for slip in run.slip_ids:
            if slip.net_payable > 0:
                acc = request.env['hr.employee.bank.account'].sudo().search([
                     ('employee_id', '=', slip.employee_id.id),
                     ('account_type', '=', 'salary')
                 ], limit=1)
                acc_num = acc.account_number if acc else "N/A"
                
                sheet_bank.write_string(row, 0, acc_num)
                sheet_bank.write(row, 1, slip.employee_id.name)
                sheet_bank.write(row, 2, slip.net_payable, money_fmt)
                
                total_transfer += slip.net_payable
                row += 1
        
        # Total
        sheet_bank.write(row, 1, "Total", label_bold_fmt)
        sheet_bank.write(row, 2, total_transfer, money_bold_fmt)
        
        workbook.close()
        output.seek(0)
        return self._make_excel_response(output, f'Termination_Run_{run.name}.xlsx')
