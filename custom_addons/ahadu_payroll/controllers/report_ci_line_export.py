# -*- coding: utf-8 -*-
import io
from odoo import http
from odoo.http import request
from odoo.tools.misc import xlsxwriter

class CashIndemnityLineExportController(http.Controller):

    @http.route('/ahadu_payroll/export_ci_lines/<int:tracking_id>', type='http', auth='user')
    def export_ci_lines(self, tracking_id, **kw):
        tracking = request.env['cash.indemnity.tracking'].browse(tracking_id)
        if not tracking.exists():
            return request.not_found()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Daily Lines')

        # Formats
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1})
        date_fmt = workbook.add_format({'num_format': 'yyyy-mm-dd', 'border': 1})
        border_fmt = workbook.add_format({'border': 1})

        # Headers
        headers = ['Date', 'Indemnity Type']
        for col, h in enumerate(headers):
            worksheet.write(0, col, h, header_fmt)
            worksheet.set_column(col, col, 20)

        # Data
        row = 1
        for line in tracking.line_ids:
            worksheet.write_datetime(row, 0, line.date, date_fmt)
            worksheet.write(row, 1, line.indemnity_type_id.name, border_fmt)
            row += 1

        workbook.close()
        output.seek(0)
        
        filename = f"CI_Lines_{tracking.employee_id.name}_{tracking.date_from}_{tracking.date_to}.xlsx"
        return request.make_response(
            output.getvalue(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', f'attachment; filename={filename};')
            ]
        )
