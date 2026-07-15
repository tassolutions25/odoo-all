from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('posted', 'Posted')
    ], string="Timesheet State", default='draft', required=True, copy=False)

    def action_submit(self):
        for line in self:
            if line.state != 'draft':
                raise UserError("Only draft timesheets can be submitted.")
            line.write({'state': 'submitted'})

    def action_approve(self):
        for line in self:
            if line.state != 'submitted':
                raise UserError("Only submitted timesheets can be approved.")
            
            # Submitter's manager check
            employee = line.employee_id
            if employee and employee.parent_id:
                current_employee = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)], limit=1)
                if not current_employee or current_employee.id != employee.parent_id.id:
                    # Bypass for PMO Admin group
                    if not self.env.user.has_group('ahadu_project_management.group_pmo_admin'):
                        raise ValidationError("Security Rule: Only the employee's manager (%s) or a PMO Admin can approve this timesheet." % employee.parent_id.name)
            else:
                # Maker checker check
                if line.user_id == self.env.user and not self.env.user.has_group('ahadu_project_management.group_pmo_admin'):
                    raise ValidationError("Maker-Checker Rule: You cannot approve your own timesheet.")

            line.write({'state': 'approved'})

    def action_post(self):
        for line in self:
            if line.state != 'approved':
                raise UserError("Only approved timesheets can be posted.")
            line.write({'state': 'posted'})

    def action_reject(self):
        for line in self:
            if line.state != 'submitted':
                raise UserError("Only submitted timesheets can be rejected.")
            line.write({'state': 'draft'})


class ProjectTask(models.Model):
    _inherit = 'project.task'

    @api.depends('timesheet_ids.unit_amount', 'timesheet_ids.state')
    def _compute_effective_hours(self):
        super(ProjectTask, self)._compute_effective_hours()
        for task in self:
            # Re-compute to only sum timesheet lines in 'approved' or 'posted' states
            approved_lines = task.timesheet_ids.filtered(lambda l: l.state in ['approved', 'posted'])
            task.effective_hours = sum(approved_lines.mapped('unit_amount'))
