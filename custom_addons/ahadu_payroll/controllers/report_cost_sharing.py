# -*- coding: utf-8 -*-
import io
import logging
from odoo import http
from odoo.http import request
from odoo.tools.misc import xlsxwriter
from .common import AhaduReportCommon

_logger = logging.getLogger(__name__)

class CostSharingReport(AhaduReportCommon):
    
    @http.route('/ahadu_payroll/cost_sharing_excel/<int:batch_id>', type='http', auth='user')
    def download_cost_sharing_excel(self, batch_id, **kw):
        """
        Implementation of Form No. 1103 Additional Declaration Form with 'Education Cost Sharing' column.
        Matches the screenshot provided by user.
        """
        batch = request.env['hr.payslip.run'].browse(batch_id)
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Cost Sharing')

        # Formats
        # Main Header: Black bg, White text
        fmt_main_header = workbook.add_format({'bold': True, 'align': 'left', 'valign': 'top', 'bg_color': 'black', 'font_color': 'white', 'font_size': 11})
        fmt_schedule = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_size': 11, 'text_wrap': True})
        
        # Section Header
        fmt_section = workbook.add_format({'bold': True, 'font_size': 10, 'top': 1})
        
        # Labels & Data
        fmt_label = workbook.add_format({'font_size': 10, 'bold': True})
        fmt_data = workbook.add_format({'font_size': 10, 'bottom': 1, 'align': 'center'})
        fmt_box_label = workbook.add_format({'font_size': 10, 'bold': False, 'border': 1, 'bg_color': '#f2f2f2', 'text_wrap': True, 'align': 'center', 'valign': 'vcenter'})
        
        # Table Formats
        fmt_th = workbook.add_format({'bold': True, 'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True, 'font_size': 9})
        fmt_td = workbook.add_format({'border': 1, 'font_size': 9, 'valign': 'vcenter'})
        fmt_td_money = workbook.add_format({'border': 1, 'font_size': 9, 'valign': 'vcenter', 'num_format': '#,##0.00'})
        fmt_td_date = workbook.add_format({'border': 1, 'font_size': 9, 'valign': 'vcenter', 'num_format': 'dd/mm/yyyy'})
        
        # --- HEADER ---
        # A1: The Federal Democratic Republic...
        worksheet.merge_range('A1:E3', "THE FEDERAL DEMOCRATIC REPUBLIC OF\nETHIOPIA\nMINISTRY OF REVENUE", fmt_main_header)
        worksheet.merge_range('F1:M3', "SCHEDULE \"A\" INCOME TAX FEE DECLARATION FORM (Form No. 1103 Additional\nDeclaration Form)\n\n(Income Tax Proclamation No. 286/1999 & Income Tax Rule No. 78/1994)", fmt_schedule)
        
        # --- SECTION 1: TAXPAYER INFORMATION ---
        worksheet.merge_range('A4:M4', "Section 1 - Taxpayer Information", fmt_section)
        
        # Row 5: Name of Person | TIN | Tax Account | Period
        worksheet.merge_range('A5:D5', "1 Name of Person or Organization Withholding Tax", fmt_label)
        worksheet.merge_range('E5:G5', "3 Taxpayer Identification Number", fmt_label)
        worksheet.merge_range('H5:K5', "4 Tax Account Number", fmt_label)
        worksheet.merge_range('L5:M5', "8 Employee Income Tax Period", fmt_th)
        
        # Row 6: Data Row 1
        worksheet.merge_range('A6:D6', "Ahadu Bank S.C", fmt_data)
        worksheet.merge_range('E6:G6', "0067033716", fmt_data) # Hardcoded TIN as per screenshot/prior tasks
        worksheet.merge_range('H6:K6', "", fmt_data)
        
        # Period Table (Month | Last date | Year)
        worksheet.write('L6', "Month", fmt_th)
        worksheet.write('M6', "Year", fmt_th) # Simplifies header
        
        # Row 7: Region | Tax Center | Period Values
        worksheet.write('A7', "2a Region", fmt_label)
        worksheet.merge_range('E7:K7', "5 Tax Center", fmt_label)
        
        m_val = batch.date_end.strftime('%B') if batch.date_end else ""
        y_val = batch.date_end.year if batch.date_end else ""
        worksheet.write('L7', m_val, fmt_data)
        worksheet.write('M7', y_val, fmt_data)
        
        # Row 8: Region Value | Tax Center Value | Doc Num
        worksheet.write('A8', "Addis Ababa", fmt_data)
        worksheet.merge_range('E8:K8', "LARG TAXPAYERS BRANCH OFFICE", fmt_data)
        worksheet.merge_range('L8:M8', "Document Number (For Official Use Only)", fmt_box_label) # Grey box
        
        # Row 9: Woreda, Zone, Kebele, House, Tel, Fax
        # Just generic placeholders to match structure
        worksheet.write('A9', "2c Woreda", fmt_label)
        worksheet.merge_range('B9:C9', "2b Zone / Kirkos", fmt_label) # Substituted
        worksheet.merge_range('D9:E9', "2d. Kebele / Farmers Association", fmt_label)
        worksheet.write('F9', "2e House Number", fmt_label)
        worksheet.merge_range('G9:H9', "6 Telephone Number", fmt_label)
        worksheet.merge_range('I9:K9', "7 Fax Number", fmt_label)
        worksheet.merge_range('L9:M9', "", workbook.add_format({'bg_color': '#bfbfbf', 'border': 1})) # Grey box
        
        # Row 10: Values
        worksheet.write('A10', "", fmt_data)
        worksheet.merge_range('B10:C10', "", fmt_data)
        worksheet.merge_range('D10:E10', "", fmt_data)
        worksheet.write('F10', "New", fmt_data) 
        worksheet.merge_range('G10:H10', "011-558-44-78", fmt_data)
        worksheet.merge_range('I10:K10', "", fmt_data)
        worksheet.merge_range('L10:M10', "", workbook.add_format({'bg_color': '#bfbfbf', 'border': 1}))
        
        # --- SECTION 2: DECLARATION DETAILS ---
        worksheet.merge_range('A11:M11', "Section 2 - Declaration Details", fmt_section)
        
        # Headers Table
        headers = [
            'a) Sequence Number', 
            'b) Employee TIN',
            'c) Name of Employee (Name, Father\'s name and Grandfather\'s name)',
            'd) Employment Date',
            'e) Gross Salary in Birr',
            'f) Transport Allowance in Birr',
            'Additional Payments', # Spans 2 cols
            'j) Total Taxable Amount (e + g + h + i)', # Wait, cols are skipped in screenshot labels?
            'k) Income Tax Amount Withheld',
            'l) Education Cost Sharing',
            'm) Net Pay',
            'Employee Signature'
        ]
        
        # Re-map Columns
        worksheet.set_column(0, 0, 5)  # Seq
        worksheet.set_column(1, 1, 15) # TIN
        worksheet.set_column(2, 2, 35) # Name
        worksheet.set_column(3, 3, 12) # Date
        worksheet.set_column(4, 4, 15) # Gross
        worksheet.set_column(5, 5, 15) # Trans
        worksheet.set_column(6, 7, 10) # Add
        worksheet.set_column(8, 8, 15) # Total
        worksheet.set_column(9, 9, 15) # Tax
        worksheet.set_column(10, 10, 15) # Cost
        worksheet.set_column(11, 11, 15) # Net
        worksheet.set_column(12, 12, 15) # Sig
        
        # Write Headers properly
        row = 12
        worksheet.write(row, 0, 'a) Sequence Number', fmt_th)
        worksheet.write(row, 1, 'b) Employee TIN', fmt_th)
        worksheet.write(row, 2, 'c) Name of Employee', fmt_th)
        worksheet.write(row, 3, 'd) Emp Date', fmt_th)
        worksheet.write(row, 4, 'e) Gross Salary', fmt_th)
        worksheet.write(row, 5, 'f) Trans. Allow.', fmt_th)
        worksheet.merge_range(row, 6, row, 7, 'Additional Payments', fmt_th)
        worksheet.write(row, 8, 'j) Total Taxable', fmt_th)
        worksheet.write(row, 9, 'k) Income Tax', fmt_th)
        worksheet.write(row, 10, 'l) Education Cost Sharing', fmt_th)
        worksheet.write(row, 11, 'm) Net Pay', fmt_th)
        worksheet.write(row, 12, 'Employee Signature', fmt_th)
        
        row += 1
        seq = 1
        total_cost_sharing = 0.0
        
        for slip in self._get_payslip_lines(batch):
            # Form 1103 logic
            basic = self._get_rule_total(slip, 'BASIC')
            trans = self._get_rule_total(slip, 'TRANS')
            tax_trans = slip._get_ahadu_taxable_transport()
            total_taxable = slip._get_ahadu_taxable_gross()
            tax = self._get_rule_total(slip, 'TAX')
            cost_share = self._get_rule_total(slip, 'COST_SHARING')
            net = self._get_rule_total(slip, 'NET')
            
            fullname = slip.employee_id.name
            start_date = slip.contract_id.date_start
            
            worksheet.write(row, 0, seq, fmt_td)
            worksheet.write(row, 1, slip.employee_id.tin_number or '', fmt_td)
            worksheet.write(row, 2, fullname, fmt_td)
            worksheet.write(row, 3, start_date if start_date else '', fmt_td_date)
            worksheet.write(row, 4, basic, fmt_td_money)
            worksheet.write(row, 5, trans, fmt_td_money)
            worksheet.write(row, 6, '', fmt_td) # Add 1
            worksheet.write(row, 7, '', fmt_td) # Add 2
            worksheet.write(row, 8, total_taxable, fmt_td_money)
            worksheet.write(row, 9, tax, fmt_td_money)
            worksheet.write(row, 10, cost_share, fmt_td_money) # This is the key column
            worksheet.write(row, 11, net, fmt_td_money)
            worksheet.write(row, 12, '', fmt_td)
            
            total_cost_sharing += cost_share
            row += 1
            seq += 1
            
        # Footer: "Total cost sharing payments"
        worksheet.merge_range(row, 0, row, 9, "Total cost sharing payments", workbook.add_format({'bold': True, 'align': 'right', 'border': 1}))
        worksheet.write(row, 10, total_cost_sharing, fmt_td_money)
        worksheet.write(row, 11, '', fmt_td)
        worksheet.write(row, 12, '', fmt_td)

        workbook.close()
        output.seek(0)
        return self._make_excel_response(output, f'Cost_Sharing_{batch.name}.xlsx')
