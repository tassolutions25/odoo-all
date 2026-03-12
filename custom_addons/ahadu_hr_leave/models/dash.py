

from odoo import models, fields, api

class HrLeaveDashboard(models.Model):
    _name = 'ahadu.hr.leave.dashboard'
    _description = 'Leave Navigation Dashboard'

    name = fields.Char(default="Dashboard")

    # These methods will be called by the buttons on our new card dashboard.
    # They find the standard Odoo actions by their XML ID and return them.

    def action_open_my_allocations(self):
        """Opens the 'My Allocations' view for the current user."""
        return self.env['ir.actions.act_window']._for_xml_id('hr_holidays.hr_leave_allocation_action_my')

    def action_open_my_time_off(self):
        """Opens the 'My Leaves' view for the current user."""
        # We find the action and can optionally customize its display name for clarity
        action = self.env['ir.actions.act_window']._for_xml_id('hr_holidays.hr_leave_action_my')
        action['display_name'] = "My Leaves"
        return action

    def action_open_overview(self):
        """Opens the 'Overview' reporting view from the Leave module."""
        return self.env['ir.actions.act_window']._for_xml_id('hr_holidays.action_hr_holidays_dashboard')

    def action_open_calendar(self):
        """Opens the main Leave calendar view."""
        return self.env['ir.actions.act_window']._for_xml_id('hr_holidays.hr_leave_action_calendar_all')

    @api.model
    def _create_dashboard_record(self):
        """
        This method is called from a data file to ensure that exactly one
        dashboard record exists for the Kanban view to display.
        """
        if not self.search([], limit=1):
            self.create({})

    # --- Fields for Leave Balances ---
    # We will compute these as a JSON field for display in the Kanban view
    leave_balances_json = fields.Text(string="Leave Balances (JSON)", compute="_compute_dashboard_values")
    
    # --- Fields for Upcoming Leaves ---
    # We use a One2many field to a helper model for the list view
    upcoming_leave_ids = fields.One2many('ahadu.upcoming.leave', 'dashboard_id', compute="_compute_dashboard_values")
    
    def _compute_dashboard_values(self):
        """
        Compute all values for the dashboard for the current user.
        This includes leave balances and the list of upcoming leaves.
        """
        for record in self:
            employee = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)], limit=1)
            
            # 1. Compute Leave Balances
            balances = self.env['hr.leave.allocation'].read_group(
                [('employee_id', '=', employee.id), ('state', '=', 'validate')],
                ['remaining_leaves:sum'],
                ['holiday_status_id']
            )
            balance_data = []
            for balance in balances:
                leave_type = self.env['hr.leave.type'].browse(balance['holiday_status_id'][0])
                balance_data.append({
                    'name': leave_type.name,
                    'days': round(balance['remaining_leaves'], 2)
                })
            record.leave_balances_json = json.dumps(balance_data)

            # 2. Compute Upcoming Leaves
            upcoming_leaves = self.env['hr.leave'].search([
                ('employee_id', '=', employee.id),
                ('date_from', '>=', fields.Date.today())
            ], order='date_from asc', limit=5)
            
            # This is a trick to populate a One2many compute field:
            # We create the records in the helper model and then link them.
            lines = []
            for leave in upcoming_leaves:
                lines.append((0, 0, {
                    'leave_type_name': leave.holiday_status_id.name,
                    'start_date': leave.date_from,
                    'end_date': leave.date_to,
                    'state': leave.state,
                }))
            
            # Clear existing lines and add the new ones
            record.upcoming_leave_ids = [(5, 0, 0)] + lines

    def action_apply_for_leave(self):
        """Opens the standard 'New Leave' request form."""
        return self.env['ir.actions.act_window']._for_xml_id('hr_holidays.hr_leave_action_new_request')

    @api.model
    def _create_dashboard_record(self):
        if not self.search([], limit=1):
            self.create({})

# --- Helper Model for the Upcoming Leaves List ---
class UpcomingLeave(models.Model):
    _name = 'ahadu.upcoming.leave'
    _description = 'Upcoming Leave Line for Dashboard'
    _transient = True # This makes it a temporary model, no table needed

    dashboard_id = fields.Many2one('ahadu.hr.leave.dashboard')
    leave_type_name = fields.Char("Leave Type")
    start_date = fields.Date("Start Date")
    end_date = fields.Date("End Date")
    state = fields.Selection([
        ('draft', 'To Submit'),
        ('confirm', 'To Approve'),
        ('refuse', 'Refused'),
        ('validate1', 'Second Approval'),
        ('validate', 'Approved')
    ], string='Status')




import json
from odoo import models, fields, api, _

class HrLeaveDashboard(models.Model):
    _name = 'ahadu.hr.leave.dashboard'
    _description = 'Leave Dashboard Data'

    name = fields.Char(default="Leave Dashboard")
    dashboard_html = fields.Html(compute='_compute_dashboard_html')

    @api.depends_context('uid')
    def _compute_dashboard_html(self):
        """Generates the HTML for the header and the leave balance cards."""
        for record in self:
            employee = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)], limit=1)
            balances = []
            if employee:
                balance_results = self.env['hr.leave.allocation'].read_group(
                    [('employee_id', '=', employee.id), ('state', '=', 'validate')],
                    ['remaining_leaves:sum'],
                    ['holiday_status_id']
                )
                balances = [
                    {'name': self.env['hr.leave.type'].browse(b['holiday_status_id'][0]).name,
                     'days': round(b['remaining_leaves'], 2)}
                    for b in balance_results
                ]
            record.dashboard_html = self.env['ir.qweb']._render(
                'ahadu_hr_leave.ahadu_leave_dashboard_balances_template',
                {'balances': balances}
            )

    def action_open_my_time_off(self):
        return self.env['ir.actions.act_window']._for_xml_id('hr_holidays.hr_leave_action_my')

    def action_open_overview(self):
        return self.env['ir.actions.act_window']._for_xml_id('hr_holidays.hr_leave_action_report_all')

    def action_open_calendar(self):
        return self.env['ir.actions.act_window']._for_xml_id('hr_holidays.hr_leave_action_calendar_all')

    @api.model
    def _get_dashboard_action(self):
        dashboard, created = self.env['ahadu.hr.leave.dashboard'].get_or_create()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Leave Dashboard',
            'res_model': 'ahadu.hr.leave.dashboard',
            'res_id': dashboard.id,
            'view_mode': 'form',
            'view_id': self.env.ref('ahadu_hr_leave.hr_leave_dashboard_view_form').id,
        }

    @api.model
    def get_or_create(self):
        dashboard = self.search([], limit=1)
        if not dashboard:
            dashboard = self.create({})
            return dashboard, True
        return dashboard, False
    



from odoo import models, fields, api

class HrLeaveDashboard(models.Model):
    _name = 'ahadu.hr.leave.dashboard'
    _description = 'Leave Navigation Dashboard'

    name = fields.Char(default="Dashboard")

    # These methods will be called by the buttons on our new card dashboard.
    # They find the standard Odoo actions by their XML ID and return them.

    def action_open_my_allocations(self):
        """Opens the 'My Allocations' view for the current user."""
        return self.env['ir.actions.act_window']._for_xml_id('hr_holidays.hr_leave_allocation_action_my')

    def action_open_my_time_off(self):
        """Opens the 'My Leaves' view for the current user."""
        # We find the action and can optionally customize its display name for clarity
        action = self.env['ir.actions.act_window']._for_xml_id('hr_holidays.hr_leave_action_my')
        action['display_name'] = "My Leaves"
        return action

    def action_open_overview(self):
        """Opens the 'Overview' reporting view from the Leave module."""
        return self.env['ir.actions.act_window']._for_xml_id('hr_holidays.action_hr_holidays_dashboard')

    def action_open_calendar(self):
        """Opens the main Leave calendar view."""
        return self.env['ir.actions.act_window']._for_xml_id('hr_holidays.hr_leave_action_calendar_all')

    @api.model
    def _create_dashboard_record(self):
        """
        This method is called from a data file to ensure that exactly one
        dashboard record exists for the Kanban view to display.
        """
        if not self.search([], limit=1):
            self.create({})

    # --- Fields for Leave Balances ---
    # We will compute these as a JSON field for display in the Kanban view
    leave_balances_json = fields.Text(string="Leave Balances (JSON)", compute="_compute_dashboard_values")
    
    # --- Fields for Upcoming Leaves ---
    # We use a One2many field to a helper model for the list view
    upcoming_leave_ids = fields.One2many('ahadu.upcoming.leave', 'dashboard_id', compute="_compute_dashboard_values")
    
    def _compute_dashboard_values(self):
        """
        Compute all values for the dashboard for the current user.
        This includes leave balances and the list of upcoming leaves.
        """
        for record in self:
            employee = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)], limit=1)
            
            # 1. Compute Leave Balances
            balances = self.env['hr.leave.allocation'].read_group(
                [('employee_id', '=', employee.id), ('state', '=', 'validate')],
                ['remaining_leaves:sum'],
                ['holiday_status_id']
            )
            balance_data = []
            for balance in balances:
                leave_type = self.env['hr.leave.type'].browse(balance['holiday_status_id'][0])
                balance_data.append({
                    'name': leave_type.name,
                    'days': round(balance['remaining_leaves'], 2)
                })
            record.leave_balances_json = json.dumps(balance_data)

            # 2. Compute Upcoming Leaves
            upcoming_leaves = self.env['hr.leave'].search([
                ('employee_id', '=', employee.id),
                ('date_from', '>=', fields.Date.today())
            ], order='date_from asc', limit=5)
            
            # This is a trick to populate a One2many compute field:
            # We create the records in the helper model and then link them.
            lines = []
            for leave in upcoming_leaves:
                lines.append((0, 0, {
                    'leave_type_name': leave.holiday_status_id.name,
                    'start_date': leave.date_from,
                    'end_date': leave.date_to,
                    'state': leave.state,
                }))
            
            # Clear existing lines and add the new ones
            record.upcoming_leave_ids = [(5, 0, 0)] + lines

    def action_apply_for_leave(self):
        """Opens the standard 'New Leave' request form."""
        return self.env['ir.actions.act_window']._for_xml_id('hr_holidays.hr_leave_action_new_request')

    @api.model
    def _create_dashboard_record(self):
        if not self.search([], limit=1):
            self.create({})

# --- Helper Model for the Upcoming Leaves List ---
class UpcomingLeave(models.Model):
    _name = 'ahadu.upcoming.leave'
    _description = 'Upcoming Leave Line for Dashboard'
    _transient = True # This makes it a temporary model, no table needed

    dashboard_id = fields.Many2one('ahadu.hr.leave.dashboard')
    leave_type_name = fields.Char("Leave Type")
    start_date = fields.Date("Start Date")
    end_date = fields.Date("End Date")
    state = fields.Selection([
        ('draft', 'To Submit'),
        ('confirm', 'To Approve'),
        ('refuse', 'Refused'),
        ('validate1', 'Second Approval'),
        ('validate', 'Approved')
    ], string='Status')