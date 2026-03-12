# -*- coding: utf-8 -*-
import io
from odoo import http
from odoo.http import request
from odoo.tools.misc import xlsxwriter
from .common import AhaduReportCommon

class ComparativeAnalyticsReport(AhaduReportCommon):

    @http.route('/ahadu_payroll/comparative_analytics_excel/<int:analytics_id>', type='http', auth='user')
    def download_comparative_analytics_excel(self, analytics_id, **kw):
        analytics = request.env['ahadu.comparative.analytics'].browse(analytics_id)
        if not analytics.exists():
            return request.not_found()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        
        # Formats
        title_fmt = workbook.add_format({'bold': True, 'size': 14, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#D3D3D3', 'border': 1})
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#4F81BD', 'font_color': 'white', 'border': 1, 'align': 'center'})
        data_fmt = workbook.add_format({'border': 1, 'align': 'left'})
        num_fmt = workbook.add_format({'border': 1, 'align': 'right', 'num_format': '#,##0'})
        money_fmt = workbook.add_format({'border': 1, 'align': 'right', 'num_format': '#,##0.00'})

        # --- SHEET 1: Summary ---
        sheet_summary = workbook.add_worksheet('Summary')
        sheet_summary.merge_range('A1:D1', 'Comparative Analytics Summary', title_fmt)
        sheet_summary.merge_range('A2:D2', 'Period: %s to %s' % (analytics.date_from, analytics.date_to), workbook.add_format({'italic': True, 'align': 'center'}))
        if analytics.branch_id:
            sheet_summary.merge_range('A3:D3', 'Branch: %s' % analytics.branch_id.name, workbook.add_format({'bold': True, 'align': 'center'}))
        
        row = 4
        sheet_summary.write(row, 0, 'Category', header_fmt)
        sheet_summary.write(row, 1, 'Current Period', header_fmt)
        sheet_summary.write(row, 2, 'Previous Period', header_fmt)
        sheet_summary.write(row, 3, 'Variance', header_fmt)
        
        sheet_summary.set_column(0, 0, 25)
        sheet_summary.set_column(1, 3, 15)

        categories = [
            ('New Additions', analytics.additions_cur, analytics.additions_prev, analytics.additions_var),
            ('Promotions', analytics.promotions_cur, analytics.promotions_prev, analytics.promotions_var),
            ('Salary Adjustments', analytics.salary_cur, analytics.salary_prev, analytics.salary_var),
            ('Transfers', analytics.transfers_cur, analytics.transfers_prev, analytics.transfers_var),
            ('Demotions', analytics.demotions_cur, analytics.demotions_prev, analytics.demotions_var),
            ('Acting', analytics.acting_cur, analytics.acting_prev, analytics.acting_var),
            ('Temporary', analytics.temporary_cur, analytics.temporary_prev, analytics.temporary_var),
            ('Terminations', analytics.terminations_cur, analytics.terminations_prev, analytics.terminations_var),
        ]

        row += 1
        for cat, cur, prev, var in categories:
            sheet_summary.write(row, 0, cat, data_fmt)
            sheet_summary.write(row, 1, cur, num_fmt)
            sheet_summary.write(row, 2, prev, num_fmt)
            sheet_summary.write(row, 3, var, num_fmt)
            row += 1

        # Helper to add details sheet
        def add_details_sheet(name, change_type, columns):
            sheet = workbook.add_worksheet(name)
            for col_idx, col_name in enumerate(columns):
                sheet.write(0, col_idx, col_name, header_fmt)
            
            # Auto-adjust column widths (basic)
            sheet.set_column(1, 1, 30) # Name
            sheet.set_column(2, 2, 12) # Date
            
            d_row = 1
            filtered_details = analytics.detail_ids.filtered(lambda d: d.change_type == change_type)
            for i, d in enumerate(filtered_details, 1):
                sheet.write(d_row, 0, i, data_fmt)
                sheet.write(d_row, 1, d.employee_id.name, data_fmt)
                sheet.write(d_row, 2, d.change_date.strftime('%Y-%m-%d') if d.change_date else '', data_fmt)
                col_i = 3
                for field in columns[3:]:
                    val = ''
                    fmt = data_fmt
                    
                    # Logic mapping based on sheet name and column index
                    if name == 'New Additions':
                        mapping = [d.to_branch_id.name, d.to_dept_id.name, d.to_division_id.name, d.to_cost_center_id.name, d.to_job_id.name, d.new_salary]
                        val = mapping[col_i-3]
                        if col_i == 8: fmt = money_fmt
                    elif name == 'Promotions':
                        mapping = [d.from_job_id.name, d.to_job_id.name, d.old_salary, d.new_salary]
                        val = mapping[col_i-3]
                        if col_i in [5, 6]: fmt = money_fmt
                    elif name in ['Transfers', 'Demotions', 'Temporary Assignments']:
                        mapping = [d.from_branch_id.name, d.to_branch_id.name, d.from_dept_id.name, d.to_dept_id.name, d.from_division_id.name, d.to_division_id.name, d.from_cost_center_id.name, d.to_cost_center_id.name, d.from_job_id.name, d.to_job_id.name]
                        val = mapping[col_i-3]
                    elif name == 'Acting Assignments':
                        mapping = [d.to_job_id.name, d.allowance_amount]
                        val = mapping[col_i-3]
                        if col_i == 4: fmt = money_fmt
                    elif name == 'Terminations':
                        val = d.description
                    
                    sheet.write(d_row, col_i, val or '', fmt)
                    col_i += 1
                d_row += 1

        # Create the sheets
        add_details_sheet('New Additions', 'addition', ['S/N', 'Employee Name', 'Date', 'Branch', 'Department', 'Division', 'Cost Center', 'Position', 'Salary'])
        add_details_sheet('Promotions', 'promotion', ['S/N', 'Employee Name', 'Date', 'From Position', 'To Position', 'From Salary', 'To Salary'])
        add_details_sheet('Transfers', 'transfer', ['S/N', 'Employee Name', 'Date', 'From Branch', 'To Branch', 'From Dept', 'To Dept', 'From Division', 'To Division', 'From Cost Center', 'To Cost Center', 'From Position', 'To Position'])
        add_details_sheet('Demotions', 'demotion', ['S/N', 'Employee Name', 'Date', 'From Branch', 'To Branch', 'From Dept', 'To Dept', 'From Division', 'To Division', 'From Cost Center', 'To Cost Center', 'From Position', 'To Position'])
        add_details_sheet('Acting Assignments', 'acting', ['S/N', 'Employee Name', 'Start Date', 'Acting Position', 'Allowance'])
        add_details_sheet('Temporary Assignments', 'temporary', ['S/N', 'Employee Name', 'Start Date', 'From Branch', 'To Branch', 'From Dept', 'To Dept', 'From Division', 'To Division', 'From Cost Center', 'To Cost Center'])
        add_details_sheet('Terminations', 'termination', ['S/N', 'Employee Name', 'Date', 'Reason'])

        workbook.close()
        output.seek(0)
        
        filename = 'Comparative_Analytics_%s_to_%s.xlsx' % (analytics.date_from, analytics.date_to)
        return self._make_excel_response(output, filename)


