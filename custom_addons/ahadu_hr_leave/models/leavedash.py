import json
from odoo import models, fields, api

class HrLeaveDashboard(models.Model):
    _name = 'ahadu.hr.leave.dashboard'
    _description = 'Leave Dashboard Data'

    name = fields.Char(default="Leave Dashboard")

    dashboard_html = fields.Html(compute='_compute_dashboard_html')

    leave_balances_json = fields.Text(string="Leave Balances (JSON)", compute="_compute_leave_balances")
    upcoming_leave_ids = fields.One2many('ahadu.upcoming.leave', 'dashboard_id', string="Upcoming Leaves")

    @api.depends_context('uid')
    def _compute_leave_balances(self):
        # This method will be called to get the balances
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
                    for b in balances
                ]

            record.dashboard_html = self.env['ir.qweb']._render(
                'ahadu_hr_leave.ahadu_leave_dashboard_template',
                {'user': self.env.user, 'balances': balances}
            )

    def action_apply_for_leave(self):
        """Opens the standard 'New Leave' request form."""
        return self.env['ir.actions.act_window']._for_xml_id('hr_holidays.hr_leave_action_new_request')

    @api.model
    def _get_dashboard_action(self):
        """This is a helper method to find or create the single dashboard record and return an action to it."""
        dashboard = self.env['ahadu.hr.leave.dashboard'].search([], limit=1)
        if not dashboard:
            dashboard = self.create({})

        # Now, compute the upcoming leaves for this record
        employee = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)], limit=1)
        if employee:
            upcoming_leaves = self.env['hr.leave'].search([
                ('employee_id', '=', employee.id),
                ('date_from', '>=', fields.Date.today())
            ], order='date_from asc', limit=5)

            # Clear old lines and create new ones
            dashboard.upcoming_leave_ids = [(5, 0, 0)] + [(0, 0, {
                'leave_type_name': leave.holiday_status_id.name,
                'start_date': leave.date_from,
                'end_date': leave.date_to,
                'state': leave.state,
            }) for leave in upcoming_leaves]

        return {
            'type': 'ir.actions.act_window',
            'name': 'Leave Dashboard',
            'res_model': 'ahadu.hr.leave.dashboard',
            'res_id': dashboard.id,
            'view_mode': 'form',
            'view_id': self.env.ref('ahadu_hr_leave.hr_leave_dashboard_view_form').id,
        }

# --- Helper Model for the Upcoming Leaves List ---
# NOTE: This is no longer transient. It will have a table to store the lines temporarily.
class UpcomingLeave(models.Model):
    _name = 'ahadu.upcoming.leave'
    _description = 'Upcoming Leave Line for Dashboard'

    dashboard_id = fields.Many2one('ahadu.hr.leave.dashboard', ondelete='cascade')
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
