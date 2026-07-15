from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ProjectTask(models.Model):
    _inherit = 'project.task'

    task_number = fields.Char(string="Task Number", readonly=True, copy=False, default="/", tracking=True)
    phase_id = fields.Many2one('project.phase', string="WBS Phase", tracking=True)
    
    # Custom Planned Dates
    planned_start_date = fields.Date(string="Planned Start Date", required=True, tracking=True)
    planned_end_date = fields.Date(string="Planned End Date", required=True, tracking=True)
    
    actual_start_date = fields.Date(string="Actual Start Date", tracking=True)
    actual_end_date = fields.Date(string="Actual End Date", tracking=True)
    
    # completion_percentage computed from subtasks if they exist, otherwise manual
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
            if task.task_status in ['completed', 'cancelled']:
                continue
            if not task.planned_start_date or not task.planned_end_date:
                continue

            t_start = task.planned_start_date
            t_end = task.planned_end_date

            # Check overlap logic
            for user in task.user_ids:
                # 1. Workload calculation from other active tasks
                overlapping_tasks = self.env['project.task'].search([
                    ('id', '!=', task.id),
                    ('user_ids', 'in', user.id),
                    ('task_status', 'in', ['assigned', 'in_progress', 'pending']),
                    ('planned_start_date', '<=', t_end),
                    ('planned_end_date', '>=', t_start)
                ])
                total_allocation = task.resource_allocation + sum(overlapping_tasks.mapped('resource_allocation'))
                if total_allocation > 100.0:
                    raise ValidationError("Capacity Breach: Assigning user %s to task %s exceeds 100%% capacity limit. Total allocated workload is %.2f%%." % (user.name, task.name, total_allocation))

                # 2. Check overlap with approved leaves
                employee = self.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)
                if employee:
                    overlapping_leaves = self.env['hr.leave'].search([
                        ('employee_id', '=', employee.id),
                        ('state', '=', 'validate'),
                        ('date_from', '<=', t_end),
                        ('date_to', '>=', t_start)
                    ])
                    if overlapping_leaves:
                        raise ValidationError("Availability Check: User %s is on approved leave during the scheduled period of this task." % user.name)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('task_number') or vals.get('task_number') == '/':
                vals['task_number'] = self.env['ir.sequence'].next_by_code('project.task.number') or '/'
        return super(ProjectTask, self).create(vals_list)

    def write(self, vals):
        for task in self:
            # Prevent edits on completed tasks unless the edit is reverting the status
            if task.task_status == 'completed' and 'task_status' not in vals:
                raise ValidationError("Security Rule: Completed tasks are locked and cannot be modified. Revert the status to modify task details.")
        return super(ProjectTask, self).write(vals)

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

        # 3. Submitter's manager (checker) – resolved via hr.employee
        submitter_employee = self.env['hr.employee'].search(
            [('user_id', '=', self.create_uid.id)], limit=1
        )
        if submitter_employee and submitter_employee.parent_id and submitter_employee.parent_id.user_id:
            recipients |= submitter_employee.parent_id.user_id.partner_id

        # 4. PMO Admins
        pmo_group = self.env.ref('ahadu_project_management.group_pmo_admin', raise_if_not_found=False)
        if pmo_group:
            recipients |= pmo_group.users.mapped('partner_id')

        # Filter to only partners with a valid email address
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

        # Send individual emails via mail.mail for guaranteed delivery
        mail_server = self.env['ir.mail_server'].search([], limit=1)
        email_from = mail_server.smtp_user if mail_server else \
            self.env['ir.config_parameter'].sudo().get_param('mail.catchall.email') or \
            'noreply@ahadu.bank'

        for partner in recipients:
            mail = self.env['mail.mail'].sudo().create({
                'subject': subject,
                'email_from': email_from,
                'email_to': partner.email,
                'body_html': body_html,
                'auto_delete': True,
            })
            mail.send()

        # Also post a chatter note for audit trail (visible in task history)
        chatter_body = """
            <p><strong>Overdue Alert Sent</strong> - This task is past its Planned End Date (%s).<br/>
            Notifications sent to: %s</p>
        """ % (self.planned_end_date, ', '.join(recipients.mapped('name')))
        self.message_post(
            body=chatter_body,
            subject=subject,
            subtype_xmlid='mail.mt_note',
            message_type='comment',
        )
