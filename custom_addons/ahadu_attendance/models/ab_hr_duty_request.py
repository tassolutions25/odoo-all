from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class HrDutyRequest(models.Model):
    _name = 'ab.hr.duty.request'
    _description = 'On Duty Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    employee_id = fields.Many2one('hr.employee', string="Employee", required=True)
    date_from = fields.Datetime(string="From", required=True)
    date_to = fields.Datetime(string="To", required=True)
    duty_location = fields.Char(string="Duty Location/Client")
    description = fields.Text(string="Description", required=True)
    state = fields.Selection([
        ('draft', 'To Submit'),
        ('confirm', 'To Approve'),
        ('approved', 'Approved'),
        ('refused', 'Refused'),
    ], string="Status", default='draft')
    # ... add approval methods similar to hr.leave ...