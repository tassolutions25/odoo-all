# ahadu_attendance/models/hr_disciplinary_note.py

from odoo import models, fields, api, _

class HrDisciplinaryNote(models.Model):
    _name = 'ab.hr.disciplinary.note'
    _description = 'Disciplinary Note'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ... (all your fields: employee_id, date, reason_type, etc.) ...
    employee_id = fields.Many2one('hr.employee', string="Employee", required=True, tracking=True)
    manager_id = fields.Many2one(related='employee_id.parent_id', string="Manager", store=True)
    company_id = fields.Many2one(related='employee_id.company_id', string="Company", store=True)
    date = fields.Date(string="Date", default=fields.Date.context_today, required=True)
    reason_type = fields.Selection([
        ('lateness', 'Repeated Lateness'),
        ('absence', 'Unauthorized Absence'),
        ('short_hours', 'Short Working Hours'),
        ('other', 'Other'),
    ], string="Reason", required=True, tracking=True)
    details = fields.Html(string="Details")
    state = fields.Selection([('draft', 'Draft'), ('sent', 'Sent')], default='draft', tracking=True)

    def action_send_note(self):
        self.ensure_one()
        # Find the template using the ID we defined in the XML file
        template = self.env.ref('ahadu_attendance.email_template_disciplinary_note', raise_if_not_found=False)
        if not template:
            # You can log a warning or just return if the template is not found
            return

        # Send the email using the found template
        template.send_mail(self.id, force_send=True)
        
        # Post a message in the record's chatter for history
        self.message_post(body=_("Disciplinary note sent to %s with CC to manager.", self.employee_id.name))
        self.write({'state': 'sent'})