import io
import base64
import xlsxwriter
from odoo import models, fields, api
from odoo.exceptions import UserError

class ProjectTimesheetReportWizard(models.TransientModel):
    _name = 'project.timesheet.report.wizard'
    _description = 'Timesheet Report Wizard'

    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    department_id = fields.Many2one('hr.department', string="Department")
    project_id = fields.Many2one('project.project', string="Project")
    employee_id = fields.Many2one('hr.employee', string="Employee")
    report_type = fields.Selection([
        ('pdf', 'PDF'),
        ('excel', 'Excel')
    ], string="Report Format", default='pdf', required=True)
    excel_file = fields.Binary(string="Excel File", readonly=True)
    excel_filename = fields.Char(string="Excel Filename", readonly=True)

    def _get_timesheet_lines(self):
        domain = [('project_id', '!=', False)]
        if self.start_date:
            domain.append(('date', '>=', self.start_date))
        if self.end_date:
            domain.append(('date', '<=', self.end_date))
        if self.project_id:
            domain.append(('project_id', '=', self.project_id.id))
        if self.employee_id:
            domain.append(('employee_id', '=', self.employee_id.id))
        if self.department_id:
            domain.append(('employee_id.department_id', '=', self.department_id.id))

        # Restrict records for PM / Direct Manager to only their respective assigned projects
        if not self.env.user.has_group('ahadu_project_management.group_pmo_admin') and not self.env.is_admin():
            domain.append(('project_id.user_id', '=', self.env.user.id))

        return self.env['account.analytic.line'].search(domain)

    def action_generate_report(self):
        self.ensure_one()
        lines = self._get_timesheet_lines()
        if not lines:
            raise UserError("No timesheet lines found for the selected filters.")

        if self.report_type == 'excel':
            return self._generate_excel_report(lines)
        else:
            return self.env.ref('ahadu_project_management.action_report_project_timesheet').report_action(self)

    def _generate_excel_report(self, lines):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Timesheet Report')

        # Formats
        title_format = workbook.add_format({
            'bold': True, 'font_size': 16, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#1F4E79', 'font_color': 'white'
        })
        header_format = workbook.add_format({
            'bold': True, 'font_size': 11, 'align': 'left', 'valign': 'vcenter', 'bg_color': '#D9E1F2', 'border': 1
        })
        cell_format = workbook.add_format({
            'font_size': 10, 'align': 'left', 'valign': 'vcenter', 'border': 1
        })
        total_format = workbook.add_format({
            'bold': True, 'font_size': 11, 'align': 'right', 'valign': 'vcenter', 'bg_color': '#E2EFDA', 'border': 1
        })

        # Set column widths
        sheet.set_column('A:A', 12)  # Date
        sheet.set_column('B:B', 20)  # Employee
        sheet.set_column('C:C', 25)  # Project
        sheet.set_column('D:D', 25)  # Task
        sheet.set_column('E:E', 35)  # Description
        sheet.set_column('F:F', 12)  # Time Spent
        sheet.set_column('G:G', 12)  # State

        # Title
        sheet.merge_range('A1:G2', 'AHADU BANK TIMESHEET REPORT', title_format)

        # Write Filters
        sheet.write('A4', 'Filters:', workbook.add_format({'bold': True}))
        filter_row = 4
        if self.start_date:
            sheet.write(filter_row, 1, f"Start: {self.start_date.strftime('%Y-%m-%d')}")
            filter_row += 1
        if self.end_date:
            sheet.write(filter_row, 1, f"End: {self.end_date.strftime('%Y-%m-%d')}")
            filter_row += 1
        if self.project_id:
            sheet.write(filter_row, 1, f"Project: {self.project_id.name}")
            filter_row += 1
        if self.department_id:
            sheet.write(filter_row, 1, f"Department: {self.department_id.name}")
            filter_row += 1

        # Table Headers
        headers = ['Date', 'Employee', 'Project', 'Task', 'Description', 'Time Spent (hrs)', 'State']
        start_row = filter_row + 2
        for col_idx, header in enumerate(headers):
            sheet.write(start_row, col_idx, header, header_format)

        # Write Data
        row = start_row + 1
        total_hours = 0.0
        for line in lines:
            sheet.write(row, 0, line.date.strftime('%Y-%m-%d') if line.date else '', cell_format)
            sheet.write(row, 1, line.employee_id.name or '', cell_format)
            sheet.write(row, 2, line.project_id.name or '', cell_format)
            sheet.write(row, 3, line.task_id.name or '', cell_format)
            sheet.write(row, 4, line.name or '', cell_format)
            sheet.write(row, 5, line.unit_amount, cell_format)
            sheet.write(row, 6, dict(line._fields['state'].selection).get(line.state, line.state), cell_format)
            total_hours += line.unit_amount
            row += 1

        # Total Row
        sheet.merge_range(f'A{row+1}:E{row+1}', 'Total Hours Spent', total_format)
        sheet.write(row, 5, total_hours, total_format)
        sheet.write(row, 6, '', total_format)

        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())

        self.write({
            'excel_file': file_data,
            'excel_filename': 'Timesheet_Report.xlsx'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model=project.timesheet.report.wizard&id={self.id}&field=excel_file&filename={self.excel_filename}&download=true',
            'target': 'new'
        }
