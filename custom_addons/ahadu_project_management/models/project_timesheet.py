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

    rejection_comment = fields.Text(string="Rejection Comment", tracking=True)

    def write(self, vals):
        # Allow state changes or modifications by PMO admin without resetting
        if self.env.user.has_group('ahadu_project_management.group_pmo_admin'):
            return super(AccountAnalyticLine, self).write(vals)

        # For other users, check if editing approved or posted lines
        for line in self:
            if line.state in ['approved', 'posted']:
                # If they are changing something other than state, reset state to draft
                if any(k not in ['state'] for k in vals):
                    vals['state'] = 'draft'
                    vals['rejection_comment'] = False # clear comment on reset
                    break
        return super(AccountAnalyticLine, self).write(vals)

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
                    # Bypass for PMO Admin group or if user is the Project Manager of the project
                    is_pm = line.project_id and line.project_id.user_id == self.env.user
                    if not is_pm and not self.env.user.has_group('ahadu_project_management.group_pmo_admin'):
                        raise ValidationError("Security Rule: Only the employee's manager (%s), Project Manager (%s), or a PMO Admin can approve this timesheet." % (employee.parent_id.name, line.project_id.user_id.name or 'N/A'))
            else:
                # Maker checker check
                is_pm = line.project_id and line.project_id.user_id == self.env.user
                if not is_pm and line.user_id == self.env.user and not self.env.user.has_group('ahadu_project_management.group_pmo_admin'):
                    raise ValidationError("Maker-Checker Rule: You cannot approve your own timesheet.")

            line.write({
                'state': 'approved',
                'rejection_comment': False # clear comment on successful approval
            })

    def action_post(self):
        for line in self:
            if line.state != 'approved':
                raise UserError("Only approved timesheets can be posted.")
            line.write({'state': 'posted'})

    def action_reject(self):
        self.ensure_one()
        if self.state != 'submitted':
            raise UserError("Only submitted timesheets can be rejected.")
        return {
            'name': 'Reject Timesheet',
            'type': 'ir.actions.act_window',
            'res_model': 'timesheet.rejection.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_line_ids': self.ids}
        }


class ProjectTask(models.Model):
    _inherit = 'project.task'

    @api.depends('timesheet_ids.unit_amount', 'timesheet_ids.state')
    def _compute_effective_hours(self):
        """
        Override to only count APPROVED or POSTED timesheet lines in the task's
        'Time Spent' total. Draft and submitted lines are excluded until approved.
        """
        if not any(self._ids):
            for task in self:
                approved_lines = task.timesheet_ids.filtered(
                    lambda l: l.state in ['approved', 'posted']
                )
                task.effective_hours = sum(approved_lines.mapped('unit_amount'))
            return
        rg = self.env['account.analytic.line']._read_group(
            [('task_id', 'in', self.ids), ('state', 'in', ['approved', 'posted'])],
            ['task_id'],
            ['unit_amount:sum'],
        )
        approved_per_task = {task.id: amount for task, amount in rg}
        for task in self:
            task.effective_hours = round(approved_per_task.get(task.id, 0.0), 2)

    total_timesheet_hours = fields.Float(
        string="Total Hours Logged",
        compute="_compute_total_timesheet_hours",
        store=True,
        help="Sum of ALL timesheet hours on this task regardless of approval state (Draft + Submitted + Approved + Posted)."
    )

    @api.depends('timesheet_ids.unit_amount')
    def _compute_total_timesheet_hours(self):
        """Sum ALL timesheet hours on this task, regardless of approval state."""
        if not any(self._ids):
            for task in self:
                task.total_timesheet_hours = sum(task.timesheet_ids.mapped('unit_amount'))
            return
        rg = self.env['account.analytic.line']._read_group(
            [('task_id', 'in', self.ids)],
            ['task_id'],
            ['unit_amount:sum'],
        )
        total_per_task = {task.id: amount for task, amount in rg}
        for task in self:
            task.total_timesheet_hours = round(total_per_task.get(task.id, 0.0), 2)


class ProjectProject(models.Model):
    _inherit = 'project.project'

    @api.depends('allow_timesheets', 'timesheet_ids.unit_amount', 'timesheet_ids.state', 'allocated_hours')
    def _compute_remaining_hours(self):
        timesheets_read_group = self.env['account.analytic.line']._read_group(
            [('project_id', 'in', self.ids), ('state', 'in', ['approved', 'posted'])],
            ['project_id'],
            ['unit_amount:sum'],
        )
        timesheet_time_dict = {project.id: unit_amount_sum for project, unit_amount_sum in timesheets_read_group}
        for project in self:
            project.effective_hours = round(timesheet_time_dict.get(project.id, 0.0), 2)
            project.remaining_hours = project.allocated_hours - project.effective_hours
            project.is_project_overtime = project.remaining_hours < 0


class TimesheetRejectionWizard(models.TransientModel):
    _name = 'timesheet.rejection.wizard'
    _description = 'Timesheet Rejection Wizard'

    line_ids = fields.Many2many('account.analytic.line', string="Timesheet Lines")
    comment = fields.Text(string="Rejection Reason", required=True)

    def action_reject(self):
        for line in self.line_ids:
            if line.state != 'submitted':
                continue
            line.write({
                'state': 'draft',
                'rejection_comment': self.comment
            })
