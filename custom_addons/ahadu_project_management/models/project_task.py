from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, time
import pytz

class ProjectTask(models.Model):
    _inherit = 'project.task'

    task_number = fields.Char(string="Task Number", readonly=True, copy=False, default="/", tracking=True)
    phase_id = fields.Many2one('project.phase', string="WBS Phase", tracking=True)
    
    planned_start_date = fields.Date(string="Planned Start Date", required=True, tracking=True)
    planned_end_date = fields.Date(string="Planned End Date", required=True, tracking=True)
    
    actual_start_date = fields.Date(string="Actual Start Date", tracking=True)
    actual_end_date = fields.Date(string="Actual End Date", tracking=True)
    
    completion_percentage = fields.Float(
        string="Completion (%)", 
        compute="_compute_completion_percentage", 
        store=True, 
        readonly=False, 
        tracking=True
    )
    
    task_status = fields.Selection([
        ('not_started', 'Not Started'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string="Task Status", default='not_started', required=True, tracking=True)

    resource_allocation = fields.Float(
        string="Workload Allocation (%)", 
        default=20.0, 
        tracking=True,
        help="Percentage of the employee's standard capacity required for this task."
    )

    is_overdue = fields.Boolean(string="Is Overdue", default=False, tracking=True)
    
    employee_allocation_info = fields.Html(
        string="Resource Allocation Summary", 
        compute="_compute_employee_allocation_summary",
        sanitize=False
    )

    @api.depends('user_ids', 'planned_start_date', 'planned_end_date', 'resource_allocation', 'task_status')
    def _compute_employee_allocation_summary(self):
        for task in self:
            if not task.user_ids or task.task_status in ['completed', 'cancelled']:
                task.employee_allocation_info = ""
                continue
            
            rows = []
            for user in task.user_ids:
                existing, total = self._get_user_load(user, task.planned_start_date, task.planned_end_date, task.id, task.resource_allocation)
                color = '#28a745' if total <= 80 else ('#ffc107' if total <= 100 else '#dc3545')
                status = '&#10003; OK' if total <= 100 else '&#9888; Over-allocated'
                rows.append(
                    "<tr>"
                    f"<td style='padding:4px 8px;border:1px solid #dee2e6;'>{user.name}</td>"
                    f"<td style='padding:4px 8px;border:1px solid #dee2e6;'>{existing:.1f}%</td>"
                    f"<td style='padding:4px 8px;border:1px solid #dee2e6;font-weight:bold;color:{color};'>{total:.1f}%</td>"
                    f"<td style='padding:4px 8px;border:1px solid #dee2e6;color:{color};'>{status}</td>"
                    "</tr>"
                )
            task.employee_allocation_info = (
                "<table style='border-collapse:collapse;font-size:13px;width:100%;'>"
                "<thead><tr style='background:#f8f9fa;'>"
                "<th style='padding:4px 8px;border:1px solid #dee2e6;'>Employee</th>"
                "<th style='padding:4px 8px;border:1px solid #dee2e6;'>Other Tasks (%)</th>"
                "<th style='padding:4px 8px;border:1px solid #dee2e6;'>Total With This Task (%)</th>"
                "<th style='padding:4px 8px;border:1px solid #dee2e6;'>Status</th>"
                "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
            )

    def _get_user_load(self, user, start, end, exclude_task_id, this_task_allocation):
        """Returns (existing_allocation, total_allocation) for a user in a date range."""
        overlapping = self.env['project.task'].search([
            ('id', '!=', exclude_task_id),
            ('user_ids', 'in', user.id),
            ('task_status', 'not in', ['completed', 'cancelled']),
            ('planned_start_date', '<=', end),
            ('planned_end_date', '>=', start),
        ])
        existing = sum(overlapping.mapped('resource_allocation'))
        return existing, existing + this_task_allocation

    @api.depends('child_ids.completion_percentage')
    def _compute_completion_percentage(self):
        for task in self:
            if task.child_ids:
                task.completion_percentage = sum(task.child_ids.mapped('completion_percentage')) / len(task.child_ids)

    @api.constrains('user_ids')
    def _check_responsible_resource(self):
        for task in self:
            if not task.user_ids:
                raise ValidationError("Task Configuration Error: Every task must have at least one responsible resource (assignee).")

    @api.constrains('completion_percentage')
    def _check_completion_percentage(self):
        for task in self:
            if task.completion_percentage < 0.0 or task.completion_percentage > 100.0:
                raise ValidationError("Validation Error: Completion Percentage must be between 0% and 100%.")

    @api.constrains('planned_start_date', 'planned_end_date', 'project_id')
    def _check_task_dates_within_project(self):
        for task in self:
            proj = task.project_id
            if proj:
                if task.planned_start_date and (task.planned_start_date < proj.planned_start_date or task.planned_start_date > proj.planned_end_date):
                    raise ValidationError("Task Planned Start Date (%s) must be within Project timeline (%s to %s)." % (task.planned_start_date, proj.planned_start_date, proj.planned_end_date))
                if task.planned_end_date and (task.planned_end_date < proj.planned_start_date or task.planned_end_date > proj.planned_end_date):
                    raise ValidationError("Task Planned End Date (%s) must be within Project timeline (%s to %s)." % (task.planned_end_date, proj.planned_start_date, proj.planned_end_date))

    @api.constrains('user_ids', 'planned_start_date', 'planned_end_date', 'resource_allocation', 'task_status')
    def _check_resource_allocation_capacity(self):
        for task in self:
            if task.task_status in ['completed', 'cancelled'] or not task.planned_start_date or not task.planned_end_date:
                continue

            tz = pytz.timezone(self.env.user.tz or 'UTC')
            dt_start = tz.localize(datetime.combine(task.planned_start_date, time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
            dt_end = tz.localize(datetime.combine(task.planned_end_date, time.max)).astimezone(pytz.UTC).replace(tzinfo=None)

            for user in task.user_ids:
                # 1. Per-employee workload check
                existing_alloc, total_alloc = self._get_user_load(
                    user, task.planned_start_date, task.planned_end_date,
                    task.id, task.resource_allocation
                )
                if total_alloc > 100.0:
                    raise ValidationError(
                        "Capacity Breach: Assigning '%s' to task '%s' would exceed 100%% capacity.\n"
                        "  \u2022 Existing allocation from other overlapping tasks: %.1f%%\n"
                        "  \u2022 This task adds: %.1f%%\n"
                        "  \u2022 Total would be: %.1f%%\n\n"
                        "Please reduce the Workload Allocation %% or adjust the task schedule."
                        % (user.name, task.name, existing_alloc, task.resource_allocation, total_alloc)
                    )

                # 2. HR Leave overlap check
                employee = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
                if employee:
                    overlapping_leaves = self.env['hr.leave'].sudo().search([
                        ('employee_id', '=', employee.id),
                        ('state', '=', 'validate'),
                        ('date_from', '<=', dt_end),
                        ('date_to', '>=', dt_start),
                    ])
                    if overlapping_leaves:
                        leave_info = ", ".join(
                            "%s \u2192 %s" % (lv.date_from.strftime('%Y-%m-%d'), lv.date_to.strftime('%Y-%m-%d'))
                            for lv in overlapping_leaves
                        )
                        raise ValidationError(
                            "Availability Check: '%s' has approved leave during the task period (%s to %s).\n"
                            "Leave period(s): %s\n\n"
                            "Please adjust the task schedule or choose a different assignee."
                            % (user.name, task.planned_start_date, task.planned_end_date, leave_info)
                        )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('task_number') or vals.get('task_number') == '/':
                vals['task_number'] = self.env['ir.sequence'].next_by_code('project.task.number') or '/'
        return super(ProjectTask, self).create(vals_list)

    def write(self, vals):
        for task in self:
            if task.task_status == 'completed' and 'task_status' not in vals:
                raise ValidationError("Security Rule: Completed tasks are locked and cannot be modified.")
        return super(ProjectTask, self).write(vals)

    def action_submit_my_timesheets(self):
        """Allow the current user to submit all their own DRAFT timesheet lines on this task."""
        self.ensure_one()
        my_draft_lines = self.timesheet_ids.filtered(
            lambda l: l.state == 'draft' and l.user_id == self.env.user
        )
        if not my_draft_lines:
            raise ValidationError("No draft timesheet lines found for you on this task.")
        my_draft_lines.action_submit()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Timesheets Submitted',
                'message': '%d timesheet line(s) submitted for approval.' % len(my_draft_lines),
                'sticky': False,
                'type': 'success',
            }
        }

    def action_add_timesheet_line(self):
        """Open the small timesheet creation form in a popup dialog box."""
        self.ensure_one()
        employee = self.env['hr.employee'].sudo().search([('user_id', '=', self.env.user.id)], limit=1)
        return {
            'name': 'Create Timesheet',
            'type': 'ir.actions.act_window',
            'res_model': 'account.analytic.line',
            'view_mode': 'form',
            'view_id': self.env.ref('hr_timesheet.timesheet_view_form_user').id,
            'target': 'new',
            'context': {
                'default_project_id': self.project_id.id,
                'default_task_id': self.id,
                'default_employee_id': employee.id if employee else False,
                'default_date': fields.Date.context_today(self),
            }
        }

    @api.model
    def _cron_check_overdue_tasks(self):
        today = fields.Date.today()
        overdue_tasks = self.search([
            ('planned_end_date', '<', today),
            ('task_status', 'not in', ['completed', 'cancelled']),
            ('is_overdue', '=', False)
        ])
        for task in overdue_tasks:
            task.is_overdue = True
            task._send_overdue_notification_email()

    def _send_overdue_notification_email(self):
        self.ensure_one()
        recipients = self.env['res.partner']

        # 1. Task Assignees
        for user in self.user_ids:
            if user.partner_id:
                recipients |= user.partner_id

        # 2. Project Manager
        if self.project_id and self.project_id.user_id and self.project_id.user_id.partner_id:
            recipients |= self.project_id.user_id.partner_id

        # 3. Submitter's manager (checker) via hr.employee
        submitter_employee = self.env['hr.employee'].search(
            [('user_id', '=', self.create_uid.id)], limit=1
        )
        if submitter_employee and submitter_employee.parent_id and submitter_employee.parent_id.user_id:
            recipients |= submitter_employee.parent_id.user_id.partner_id

        # 4. PMO Admins
        pmo_group = self.env.ref('ahadu_project_management.group_pmo_admin', raise_if_not_found=False)
        if pmo_group:
            recipients |= pmo_group.users.mapped('partner_id')

        # Filter to partners with a valid email address
        recipients = recipients.filtered(lambda p: p.email)
        if not recipients:
            return

        subject = "Overdue Task Alert: %s [%s]" % (self.name, self.task_number)
        body_html = """
            <p>Dear All,</p>
            <p>The following project task is <strong>overdue</strong> and requires your attention:</p>
            <table style="border-collapse:collapse;width:100%%;font-family:Arial,sans-serif;">
                <tr style="background:#f44336;color:#fff;">
                    <th style="padding:8px;text-align:left;">Field</th>
                    <th style="padding:8px;text-align:left;">Value</th>
                </tr>
                <tr><td style="padding:6px;border:1px solid #ddd;"><strong>Task ID</strong></td>
                    <td style="padding:6px;border:1px solid #ddd;">%s</td></tr>
                <tr><td style="padding:6px;border:1px solid #ddd;"><strong>Task Name</strong></td>
                    <td style="padding:6px;border:1px solid #ddd;">%s</td></tr>
                <tr><td style="padding:6px;border:1px solid #ddd;"><strong>Project</strong></td>
                    <td style="padding:6px;border:1px solid #ddd;">%s</td></tr>
                <tr><td style="padding:6px;border:1px solid #ddd;"><strong>Status</strong></td>
                    <td style="padding:6px;border:1px solid #ddd;">%s</td></tr>
                <tr style="background:#ffebee;"><td style="padding:6px;border:1px solid #ddd;"><strong>Planned End Date</strong></td>
                    <td style="padding:6px;border:1px solid #ddd;color:#f44336;"><strong>%s</strong></td></tr>
            </table>
            <br/>
            <p>Please take immediate action: update the task status or revise the planned timeline.</p>
            <p style="color:#888;font-size:12px;">This is an automated alert from Ahadu Bank Project Management System.</p>
        """ % (
            self.task_number,
            self.name,
            self.project_id.name if self.project_id else 'N/A',
            dict(self._fields['task_status'].selection).get(self.task_status, self.task_status),
            self.planned_end_date,
        )

        # Send via mail.mail for guaranteed SMTP delivery (bypasses follower checks)
        mail_server = self.env['ir.mail_server'].search([], limit=1)
        email_from = mail_server.smtp_user if mail_server else (
            self.env['ir.config_parameter'].sudo().get_param('mail.catchall.email') or 'noreply@ahadu.bank'
        )
        for partner in recipients:
            self.env['mail.mail'].sudo().create({
                'subject': subject,
                'email_from': email_from,
                'email_to': partner.email,
                'body_html': body_html,
                'auto_delete': True,
            }).send()

        # Chatter audit note
        chatter_body = "<p><strong>Overdue Alert Sent</strong> — Task is past Planned End Date (%s).<br/>Notified: %s</p>" % (
            self.planned_end_date, ', '.join(recipients.mapped('name'))
        )
        self.message_post(
            body=chatter_body,
            subject=subject,
            subtype_xmlid='mail.mt_note',
            message_type='comment',
        )
