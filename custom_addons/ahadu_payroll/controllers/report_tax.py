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

class TaxReport(AhaduReportCommon):
    
    @http.route('/ahadu_payroll/tax_declaration/<int:batch_id>', type='http', auth='user')
    def download_tax_declaration(self, batch_id, **kw):
        batch = request.env['hr.payslip.run'].browse(batch_id)
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Tax Report')

        # --- Formats ---
        bold_center = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'text_wrap': True})
        header_gray = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1, 'align': 'center', 'text_wrap': True, 'font_size': 9})
        border_fmt = workbook.add_format({'border': 1, 'font_size': 9})
        money_fmt = workbook.add_format({'num_format': '#,##0.00', 'border': 1, 'font_size': 9})
        date_fmt = workbook.add_format({'num_format': 'dd/mm/yyyy', 'border': 1, 'font_size': 9})
        
        try:
            # Use Odoo's built-in resource finder
            image_path = get_module_resource('ahadu_payroll', 'src', 'images', 'Ahadu Bank Logo with Name.jpg')
            
            if image_path and os.path.exists(image_path):
                # Insert image centered in the merged range A1:L1 roughly
                worksheet.set_row(0, 70) # Increase height of first row
                worksheet.merge_range('A1:L1', "") # Clear text
                worksheet.insert_image('D1', image_path, {'x_scale': 0.6, 'y_scale': 0.6, 'x_offset': 15, 'y_offset': 5})
            else:
                # Fallback to text if image missing
                worksheet.merge_range('A1:L1', "Ahadu Bank S.C", workbook.add_format({'bold': True, 'size': 16, 'align': 'center', 'font_color': '#840036'}))
        except Exception as e:
            _logger.error(f"Failed to insert logo: {str(e)}")
            # Fallback on error
            worksheet.merge_range('A1:L1', "Ahadu Bank S.C", workbook.add_format({'bold': True, 'size': 16, 'align': 'center', 'font_color': '#840036'}))
        
        month_name = batch.date_start.strftime('%B %Y') if batch.date_start else ''
        worksheet.merge_range('A2:L2', "Employee Income Tax Report", workbook.add_format({'bold': True, 'size': 12, 'align': 'center'}))
        worksheet.merge_range('A3:L3', f"For the month of {month_name}", workbook.add_format({'bold': True, 'italic': True, 'align': 'center'}))

        # --- Columns ---
        headers = [
            "Employee's TIN", 
            "Employee Full Name", 
            "Start Date", 
            "End Date", 
            "Basic Salary", 
            "Transport Allowance", 
            "Taxable Transport Allowance", 
            "Overtime", 
            "Other Taxable Benefits", 
            "Total Taxable", 
            "Tax Withheld", 
            "Cost Sharing"
        ]
        
        row = 4
        for col, h in enumerate(headers):
            worksheet.write(row, col, h, header_gray)
            # Adjust widths
            if col == 1: # Name
                worksheet.set_column(col, col, 30)
            elif col in [0, 2, 3]: # Dates/TIN
                worksheet.set_column(col, col, 12)
            else: # Money columns
                worksheet.set_column(col, col, 15)

        row += 1
        
        # --- Data Rows ---
        totals = {k: 0.0 for k in ['basic', 'trans', 'tax_trans', 'ot', 'other_taxable', 'total_taxable', 'tax', 'cost_sharing']}

        for slip in self._get_payslip_lines(batch):
            # 1. Basic Salary (Earnings)
            basic = self._get_rule_total(slip, 'BASIC')
            
            # 2. Transport
            trans = self._get_rule_total(slip, 'TRANS')
            
            # 3. Taxable Transport
            tax_trans = slip._get_ahadu_taxable_transport()
            
            # 4. Overtime (Assuming rule code 'OT_125', 'OT_150' etc sum up to category 'OT' or specific rule)
            # For now getting specific rule total if exists, or passed from other field
            ot = self._get_rule_total(slip, 'OT')
            
            # 5. Total Taxable Income
            total_taxable = slip._get_ahadu_taxable_gross()
            
            # 6. Other Taxable Benefits = Total Taxable - (Basic + Taxable Trans + OT)
            # This ensures the equation balances: Total = Sum of parts
            # Note: Basic here means the Taxable Basic (after Leave Deduction usually). 
            # But let's check _get_ahadu_taxable_gross definition:
            # Taxable = (Basic - Penalty) + Taxable Trans + Rep + Housing + Mobile + LOP Adj
            # So "Other Taxable" effectively includes Rep + Housing + Mobile + LOP Adj - Penalty impact
            other_taxable = total_taxable - basic - tax_trans - ot
            
            # 7. Tax
            tax = self._get_rule_total(slip, 'TAX')
            
            # 8. Cost Sharing
            c_share = self._get_rule_total(slip, 'COST_SHARING')
            
            # Witing Data
            worksheet.write(row, 0, slip.employee_id.tin_number or '', border_fmt) # TIN
            worksheet.write(row, 1, slip.employee_id.name, border_fmt)
            
            start_date = slip.contract_id.date_start
            end_date = slip.contract_id.date_end
            
            worksheet.write(row, 2, start_date.strftime('%d/%m/%Y') if start_date else '', date_fmt)
            worksheet.write(row, 3, end_date.strftime('%d/%m/%Y') if end_date else '', date_fmt)
            
            worksheet.write(row, 4, basic, money_fmt)
            worksheet.write(row, 5, trans, money_fmt)
            worksheet.write(row, 6, tax_trans, money_fmt)
            worksheet.write(row, 7, ot, money_fmt)
            worksheet.write(row, 8, other_taxable, money_fmt)
            worksheet.write(row, 9, total_taxable, money_fmt)
            worksheet.write(row, 10, tax, money_fmt)
            worksheet.write(row, 11, c_share, money_fmt)
            
            # Aggregate Totals
            totals['basic'] += basic
            totals['trans'] += trans
            totals['tax_trans'] += tax_trans
            totals['ot'] += ot
            totals['other_taxable'] += other_taxable
            totals['total_taxable'] += total_taxable
            totals['tax'] += tax
            totals['cost_sharing'] += c_share
            
            row += 1

        # --- Totals Row ---
        worksheet.merge_range(row, 0, row, 3, 'Total', workbook.add_format({'bold': True, 'align': 'right', 'border': 1}))
        worksheet.write(row, 4, totals['basic'], money_fmt)
        worksheet.write(row, 5, totals['trans'], money_fmt)
        worksheet.write(row, 6, totals['tax_trans'], money_fmt)
        worksheet.write(row, 7, totals['ot'], money_fmt)
        worksheet.write(row, 8, totals['other_taxable'], money_fmt)
        worksheet.write(row, 9, totals['total_taxable'], money_fmt)
        worksheet.write(row, 10, totals['tax'], money_fmt)
        worksheet.write(row, 11, totals['cost_sharing'], money_fmt)
        
        row += 2
        
        # --- Footer / Signatures ---
        worksheet.write(row, 0, "Approved By:", workbook.add_format({'bold': True}))
        # Check if we have approved_by_id from previous task
        approver = batch.approved_by_id.name if 'approved_by_id' in batch else "____________________"
        worksheet.write(row, 2, approver)
        
        worksheet.write(row, 4, "Date:", workbook.add_format({'bold': True}))
        app_date = batch.approved_date.strftime('%d/%m/%Y') if 'approved_date' in batch and batch.approved_date else "____________________"
        worksheet.write(row, 5, app_date)

        workbook.close(); output.seek(0)
        return self._make_excel_response(output, f'Tax_Report_{batch.name}.xlsx')
