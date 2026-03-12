from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class HrAttendanceSheet(models.Model):
    _name = 'ab.hr.attendance.sheet'
    _description = 'Attendance Sheet for Approval'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc'


     # Ensure the 'inverse_name' is correct.
    attendance_ids = fields.One2many(
        'hr.attendance',          # The model this field links TO
        'attendance_sheet_id',    # The Many2one field ON the hr.attendance model
        string="Attendances"
    )

    name = fields.Char(compute='_compute_name', store=True)
    employee_id = fields.Many2one('hr.employee', string="Employee", required=True, readonly=True, states={'draft': [('readonly', False)]})
    manager_id = fields.Many2one(related='employee_id.parent_id', string="Manager", store=True)
    date_from = fields.Date(string="Date From", required=True, readonly=True, states={'draft': [('readonly', False)]})
    date_to = fields.Date(string="Date To", required=True, readonly=True, states={'draft': [('readonly', False)]})
    
    total_worked_hours = fields.Float(compute='_compute_totals', store=True, string="Total Worked Hours")
    total_late_minutes = fields.Float(compute='_compute_totals', store=True, string="Total Late (Minutes)")
    total_unauthorized_absence = fields.Integer(compute='_compute_totals', store=True, string="Unauthorized Absences")

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string="Status", default='draft', tracking=True)

    @api.constrains('date_from', 'date_to', 'employee_id')
    def _check_dates(self):
        for sheet in self:
            if sheet.date_from > sheet.date_to:
                raise ValidationError(_("The start date cannot be after the end date."))
            domain = [
                ('id', '!=', sheet.id),
                ('employee_id', '=', sheet.employee_id.id),
                ('date_from', '<=', sheet.date_to),
                ('date_to', '>=', sheet.date_from),
            ]
            if self.search_count(domain):
                raise ValidationError(_("You cannot have overlapping attendance sheets for the same employee."))

    @api.depends('employee_id', 'date_from', 'date_to')
    def _compute_name(self):
        for sheet in self:
            if sheet.employee_id and sheet.date_from and sheet.date_to:
                sheet.name = f"Attendance for {sheet.employee_id.name} ({sheet.date_from} to {sheet.date_to})"
            else:
                sheet.name = _("New Attendance Sheet")

    @api.depends('attendance_ids.worked_hours', 'attendance_ids.late_minutes')
    def _compute_totals(self):
        for sheet in self:
            sheet.total_worked_hours = sum(sheet.attendance_ids.mapped('worked_hours'))
            sheet.total_late_minutes = sum(sheet.attendance_ids.mapped('late_minutes'))
            # Placeholder for absence calculation, which is better done via a dedicated cron/reporting
            sheet.total_unauthorized_absence = self.env['hr.disciplinary.note'].search_count([
                ('employee_id', '=', sheet.employee_id.id),
                ('reason_type', '=', 'absence'),
                ('date', '>=', sheet.date_from),
                ('date', '<=', sheet.date_to),
            ])

    def action_get_attendances(self):
        self.ensure_one()
        attendances = self.env['hr.attendance'].search([
            ('employee_id', '=', self.employee_id.id),
            ('check_in', '>=', self.date_from),
            ('check_in', '<=', self.date_to),
            ('attendance_sheet_id', '=', False),
        ])
        attendances.write({'attendance_sheet_id': self.id})

    def action_submit(self):
        self.state = 'submitted'
        if self.manager_id.user_id:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_('Approve Attendance Sheet'),
                user_id=self.manager_id.user_id.id
            )

    def action_approve(self):
        if self.env.user != self.manager_id.user_id and not self.env.user.has_group('hr.group_hr_manager'):
            raise UserError(_("Only the employee's manager or an HR Manager can approve this sheet."))
        self.activity_feedback(['mail.mail_activity_data_todo'])
        self.state = 'approved'

    def action_reject(self):
        self.activity_feedback(['mail.mail_activity_data_todo'])
        self.state = 'rejected'
    
    def action_to_draft(self):
        self.state = 'draft'