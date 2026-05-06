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

class BonusTaxReport(AhaduReportCommon):
    
    @http.route('/ahadu_payroll/bonus_tax_declaration/<int:batch_id>', type='http', auth='user')
    def download_bonus_tax_declaration(self, batch_id, **kw):
        batch = request.env['ahadu.bonus.payment'].browse(batch_id)
        if not batch.exists():
            return request.not_found()
            
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Tax Report')

        # --- Formats ---
        bold_center = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'text_wrap': True})
        header_gray = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True, 'font_size': 9})
        border_fmt = workbook.add_format({'border': 1, 'font_size': 9, 'valign': 'vcenter'})
        money_fmt = workbook.add_format({'num_format': '#,##0.00', 'border': 1, 'font_size': 9, 'valign': 'vcenter'})
        date_fmt = workbook.add_format({'num_format': 'dd/mm/yyyy', 'border': 1, 'font_size': 9, 'valign': 'vcenter', 'align': 'center'})
        
        try:
            image_path = get_module_resource('ahadu_payroll', 'src', 'images', 'Ahadu Bank Logo with Name.jpg')
            if image_path and os.path.exists(image_path):
                worksheet.set_row(0, 70)
                worksheet.merge_range('A1:L1', "")
                worksheet.insert_image('D1', image_path, {'x_scale': 0.6, 'y_scale': 0.6, 'x_offset': 15, 'y_offset': 5})
            else:
                worksheet.merge_range('A1:L1', "Ahadu Bank S.C", workbook.add_format({'bold': True, 'size': 16, 'align': 'center', 'font_color': '#840036'}))
        except Exception as e:
            _logger.error(f"Failed to insert logo: {str(e)}")
            worksheet.merge_range('A1:L1', "Ahadu Bank S.C", workbook.add_format({'bold': True, 'size': 16, 'align': 'center', 'font_color': '#840036'}))
        
        worksheet.merge_range('A2:L2', "Employee Income Tax (Bonus Payment)", workbook.add_format({'bold': True, 'size': 12, 'align': 'center'}))
        worksheet.merge_range('A3:L3', f"Batch: {batch.name} | Date: {batch.date.strftime('%d %B %Y') if batch.date else ''}", workbook.add_format({'bold': True, 'italic': True, 'align': 'center'}))

        # --- Columns (Matching Payslip Tax Declaration) ---
        headers = [
            "Employee's TIN", 
            "Employee Full Name", 
            "Start Date", 
            "End Date", 
            "Basic Salary", 
            "Transport Allowance", 
            "Taxable Transport Allowance", 
            "Overtime", 
            "Other Taxables (Bonus)", 
            "Total Taxable", 
            "Tax Withheld", 
            "Cost Sharing"
        ]
        
        row = 4
        for col, h in enumerate(headers):
            worksheet.write(row, col, h, header_gray)
            if col == 1: worksheet.set_column(col, col, 30)
            elif col in [0, 2, 3]: worksheet.set_column(col, col, 12)
            else: worksheet.set_column(col, col, 15)

        row += 1
        totals = {k: 0.0 for k in ['basic', 'trans', 'tax_trans', 'ot', 'other_taxable', 'total_taxable', 'tax', 'cost_sharing']}

        for line in batch.line_ids:
            bonus_amt = line.bonus_amount
            bonus_tax = line.bonus_tax
            
            if abs(bonus_amt) > 0.01:
                worksheet.write(row, 0, line.employee_id.tin_number or '', border_fmt)
                worksheet.write(row, 1, line.employee_id.name, border_fmt)
                
                # Use batch date as proxy
                worksheet.write(row, 2, batch.date.strftime('%d/%m/%Y'), date_fmt)
                worksheet.write(row, 3, batch.date.strftime('%d/%m/%Y'), date_fmt)
                
                # Match the income tax report format
                # We show the regular basic as well since it was part of the tax calculation baseline
                basic = line.salary_paid_during_mid
                # Total taxable = basic + bonus (simplified view)
                # Actually, the tax reported is just the INCREMENTAL tax for the bonus.
                total_taxable = basic + bonus_amt
                
                worksheet.write(row, 4, basic, money_fmt)
                worksheet.write(row, 5, 0.0, money_fmt)
                worksheet.write(row, 6, 0.0, money_fmt)
                worksheet.write(row, 7, 0.0, money_fmt)
                worksheet.write(row, 8, bonus_amt, money_fmt)
                worksheet.write(row, 9, total_taxable, money_fmt)
                worksheet.write(row, 10, bonus_tax, money_fmt) # Incremental Bonus Tax
                worksheet.write(row, 11, 0.0, money_fmt)
                
                totals['basic'] += basic
                totals['other_taxable'] += bonus_amt
                totals['total_taxable'] += total_taxable
                totals['tax'] += bonus_tax
                
                row += 1

        # --- Totals Row ---
        worksheet.merge_range(row, 0, row, 3, 'Total', workbook.add_format({'bold': True, 'align': 'right', 'border': 1}))
        worksheet.write(row, 4, totals['basic'], money_fmt)
        worksheet.write(row, 5, 0.0, money_fmt)
        worksheet.write(row, 6, 0.0, money_fmt)
        worksheet.write(row, 7, 0.0, money_fmt)
        worksheet.write(row, 8, totals['other_taxable'], money_fmt)
        worksheet.write(row, 9, totals['total_taxable'], money_fmt)
        worksheet.write(row, 10, totals['tax'], money_fmt)
        worksheet.write(row, 11, 0.0, money_fmt)
        
        row += 2
        worksheet.write(row, 0, "Approved By:", workbook.add_format({'bold': True}))
        approver = batch.approved_by_id.name or "____________________"
        worksheet.write(row, 2, approver)
        worksheet.write(row, 4, "Date:", workbook.add_format({'bold': True}))
        app_date = batch.approved_on.strftime('%d/%m/%Y') if batch.approved_on else "____________________"
        worksheet.write(row, 5, app_date)

        workbook.close(); output.seek(0)
        return self._make_excel_response(output, f'Bonus_Tax_Report_{batch.name}.xlsx')
