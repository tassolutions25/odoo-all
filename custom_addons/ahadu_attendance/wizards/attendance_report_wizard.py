# -*- coding: utf-8 -*-
import json
from odoo import models, fields, api, _
from odoo.tools import date_utils, json_default
from odoo.exceptions import UserError
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from odoo.tools import date_utils

class AttendanceReportWizard(models.TransientModel):
    _name = 'attendance.report.wizard'
    _description = 'Advanced Attendance Report Wizard'

    def _get_default_start_date(self):
        return date.today().replace(day=1)

    def _get_default_end_date(self):
        return date.today()

    # --- Main Filters ---
    date_from = fields.Date(string="Start Date", required=True, default=_get_default_start_date)
    date_to = fields.Date(string="End Date", required=True, default=_get_default_end_date)
    
    # New: Date range presets
    date_range_type = fields.Selection([
        ('today', 'Today'), ('week', 'This Week'),
        ('month', 'This Month'), ('quarter', 'This Quarter'),
        ('year', 'This Year'), ('custom', 'Custom Range'),
    ], string="Date Range", default='month')

    # New: Report Type
    report_type = fields.Selection([
        ('all', 'All Employees'),
        ('department', 'By Department'),
        ('employee', 'Specific Employees'),
        ('summary', 'Summary & Ranking Report'),
        ('department_summary', 'Departmental Summary & Ranking'),
        ('branch', 'By Branch'),
        ('branch_summary', 'Branch Summary'),
        ('lunch_tracking', 'Lunch Time Report'),
    ], string="Report Type", default='all', required=True)

    lunch_scope = fields.Selection([
        ('all', 'All Employees'),
        ('department', 'By Department'),
        ('branch', 'By Branch'),
    ], string="Lunch Report Scope", default='all')

    summary_ranking_type = fields.Selection([
        ('most_present', 'Most Present'),
        ('most_absent', 'Most Absent'),
        ('most_late', 'Most Late'),
        ('most_early_out', 'Most Early Out'),
    ], string="Rank By", default='most_present',
       help="Choose the metric for ranking employees.")


    # --- Conditional Fields ---
    department_ids = fields.Many2many('hr.department', string="Departments",
                                      help="Select one or more departments. Required if reporting 'By Department'.")
    branch_ids = fields.Many2many(
        'hr.branch',
        string="Branches",
        help="Select one or more branches for branch-based reports."
    )
    employee_ids = fields.Many2many('hr.employee', string="Employees",
                                    help="Select one or more employees. Required if reporting on 'Specific Employees'.")
    
    # New: Option to download as a ZIP file
    download_as_zip = fields.Boolean(string="Download Each Department as Separate File (ZIP)",
                                     help="If checked, a ZIP file will be generated with one Excel file per selected department.")

    @api.onchange('date_range_type')
    def _onchange_date_range_type(self):
        today = date.today()
        if self.date_range_type == 'today':
            self.date_from = today
            self.date_to = today
        elif self.date_range_type == 'week':
            self.date_from = today - timedelta(days=today.weekday())
            self.date_to = self.date_from + timedelta(days=6)
        elif self.date_range_type == 'month':
            self.date_from = today.replace(day=1)
            self.date_to = (self.date_from + relativedelta(months=1)) - timedelta(days=1)
        elif self.date_range_type == 'quarter':
            quarter_start_month = (today.month - 1) // 3 * 3 + 1
            self.date_from = today.replace(month=quarter_start_month, day=1)
            self.date_to = (self.date_from + relativedelta(months=3)) - timedelta(days=1)
        elif self.date_range_type == 'year':
            self.date_from = today.replace(month=1, day=1)
            self.date_to = today.replace(month=12, day=31)

    def action_print_report(self):
        # This will now call the controller with all the necessary data
        self.ensure_one()
        data = self.read()[0]
        json_data = json.dumps(data, default=json_default)
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/attendance/excel_report?wizard_data={json_data}',
            'target': 'self',
        }