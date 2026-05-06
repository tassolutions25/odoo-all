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

class BackpayTaxReport(AhaduReportCommon):
    
    @http.route('/ahadu_payroll/backpay_tax_declaration/<int:batch_id>', type='http', auth='user')
    def download_backpay_tax_declaration(self, batch_id, **kw):
        batch = request.env['ahadu.backpay.batch'].browse(batch_id)
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
        
        month_label = dict(batch._fields['month'].selection).get(batch.month)
        worksheet.merge_range('A2:L2', "Employee Income Tax - Backpay (Arrears)", workbook.add_format({'bold': True, 'size': 12, 'align': 'center'}))
        worksheet.merge_range('A3:L3', f"Batch: {batch.name} | Month: {month_label} {batch.year}", workbook.add_format({'bold': True, 'italic': True, 'align': 'center'}))

        # --- Columns ---
        headers = [
            "Employee's TIN", 
            "Employee Full Name", 
            "Start Date", 
            "End Date", 
            "Arrears Basic", 
            "Arrears Transport", 
            "Taxable Arrears Trans", 
            "Arrears Overtime", 
            "Other Taxable Arrears", 
            "Total Taxable Arrears", 
            "Tax Withheld (Arrears)", 
            "Arrears Cost Sharing"
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
            basic = line.diff_basic
            trans = line.diff_transport
            tax_trans = line.diff_taxable_transport
            ot = line.diff_ot
            total_taxable = line.diff_taxable_gross
            # Other Taxable = Total - (Basic + Taxable Trans + OT)
            other_taxable = total_taxable - basic - tax_trans - ot
            tax = line.diff_tax
            c_share = line.diff_cost_sharing
            
            # Only include lines with significant differences
            if abs(total_taxable) > 0.01 or abs(tax) > 0.01:
                worksheet.write(row, 0, line.employee_id.tin_number or '', border_fmt)
                worksheet.write(row, 1, line.employee_id.name, border_fmt)
                
                # Use payslip dates as proxy for reporting period
                p_start = line.payslip_id.date_from if line.payslip_id else False
                p_end = line.payslip_id.date_to if line.payslip_id else False
                
                worksheet.write(row, 2, p_start.strftime('%d/%m/%Y') if p_start else '', date_fmt)
                worksheet.write(row, 3, p_end.strftime('%d/%m/%Y') if p_end else '', date_fmt)
                
                worksheet.write(row, 4, basic, money_fmt)
                worksheet.write(row, 5, trans, money_fmt)
                worksheet.write(row, 6, tax_trans, money_fmt)
                worksheet.write(row, 7, ot, money_fmt)
                worksheet.write(row, 8, other_taxable, money_fmt)
                worksheet.write(row, 9, total_taxable, money_fmt)
                worksheet.write(row, 10, tax, money_fmt)
                worksheet.write(row, 11, c_share, money_fmt)
                
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
        worksheet.write(row, 0, "Approved By:", workbook.add_format({'bold': True}))
        approver = batch.approved_by_id.name or "____________________"
        worksheet.write(row, 2, approver)
        worksheet.write(row, 4, "Date:", workbook.add_format({'bold': True}))
        app_date = batch.approved_on.strftime('%d/%m/%Y') if batch.approved_on else "____________________"
        worksheet.write(row, 5, app_date)

        workbook.close(); output.seek(0)
        return self._make_excel_response(output, f'Backpay_Tax_Report_{batch.name}.xlsx')
