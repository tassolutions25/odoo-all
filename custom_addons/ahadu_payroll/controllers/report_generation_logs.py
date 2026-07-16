# -*- coding: utf-8 -*-
import io
import logging
from odoo import http
from odoo.http import request
from .common import AhaduReportCommon
from odoo.tools.misc import xlsxwriter

_logger = logging.getLogger(__name__)


class GenerationLogsExportController(AhaduReportCommon):

    @http.route('/ahadu_payroll/generation_logs/<int:batch_id>', type='http', auth='user')
    def export_generation_logs(self, batch_id, **kw):
        batch = request.env['hr.payslip.run'].browse(batch_id)
        if not batch.exists():
            return request.not_found()

        missed_lines = batch.missed_reason_ids
        if not missed_lines:
            return request.not_found()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Generation Logs')

        # ── Formats ──
        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 14, 'align': 'center',
            'valign': 'vcenter', 'font_color': '#FFFFFF',
            'bg_color': '#2E4053', 'border': 1,
        })
        subtitle_fmt = workbook.add_format({
            'bold': True, 'font_size': 11, 'align': 'center',
            'valign': 'vcenter', 'italic': True,
            'bg_color': '#D5DBDB', 'border': 1,
        })
        header_fmt = workbook.add_format({
            'bold': True, 'font_size': 10, 'align': 'center',
            'valign': 'vcenter', 'font_color': '#FFFFFF',
            'bg_color': '#1A5276', 'border': 1, 'text_wrap': True,
        })
        data_fmt = workbook.add_format({
            'font_size': 10, 'border': 1, 'valign': 'vcenter',
        })
        data_center_fmt = workbook.add_format({
            'font_size': 10, 'border': 1, 'align': 'center',
            'valign': 'vcenter',
        })
        reason_fmt = workbook.add_format({
            'font_size': 10, 'border': 1, 'valign': 'vcenter',
            'text_wrap': True, 'font_color': '#922B21',
        })

        # ── Column Widths ──
        col_widths = [6, 18, 35, 25, 30, 25, 45]
        for i, w in enumerate(col_widths):
            worksheet.set_column(i, i, w)

        # ── Title Row ──
        worksheet.merge_range('A1:G1', 'Payslip Generation Logs', title_fmt)
        worksheet.set_row(0, 30)

        # ── Subtitle Row ──
        subtitle = f"Batch: {batch.name}"
        if batch.date_start and batch.date_end:
            subtitle += f"  |  Period: {batch.date_start.strftime('%d/%m/%Y')} - {batch.date_end.strftime('%d/%m/%Y')}"
        worksheet.merge_range('A2:G2', subtitle, subtitle_fmt)
        worksheet.set_row(1, 22)

        # ── Headers ──
        headers = ['#', 'Employee ID', 'Employee Name', 'Branch', 'Department', 'Salary Account', 'Reason']
        for col, h in enumerate(headers):
            worksheet.write(2, col, h, header_fmt)
        worksheet.set_row(2, 22)

        # ── Data Rows ──
        row = 3
        for idx, line in enumerate(missed_lines, start=1):
            emp = line.employee_id
            worksheet.write(row, 0, idx, data_center_fmt)
            worksheet.write(row, 1, emp.employee_id or '', data_center_fmt)
            worksheet.write(row, 2, emp.name or '', data_fmt)
            worksheet.write(row, 3, emp.branch_id.name if emp.branch_id else '', data_fmt)
            worksheet.write(row, 4, emp.department_id.name if emp.department_id else '', data_fmt)
            worksheet.write(row, 5, line.salary_account or 'UNKNOWN', data_center_fmt)
            worksheet.write(row, 6, line.reason or '', reason_fmt)
            row += 1

        # ── Summary footer ──
        summary_fmt = workbook.add_format({
            'bold': True, 'font_size': 10, 'align': 'right',
            'valign': 'vcenter', 'bg_color': '#F2F3F4', 'border': 1,
        })
        summary_val_fmt = workbook.add_format({
            'bold': True, 'font_size': 10, 'align': 'center',
            'valign': 'vcenter', 'bg_color': '#F2F3F4', 'border': 1,
        })
        worksheet.merge_range(row, 0, row, 5, 'Total Skipped Employees:', summary_fmt)
        worksheet.write(row, 6, len(missed_lines), summary_val_fmt)

        workbook.close()
        output.seek(0)

        filename = f"Generation_Logs_{batch.name.replace(' ', '_')}.xlsx"
        return self._make_excel_response(output, filename)
