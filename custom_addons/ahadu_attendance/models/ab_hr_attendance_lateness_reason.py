from odoo import models, fields

class HrAttendanceLatenessReason(models.Model):
    _name = 'ab.hr.attendance.lateness.reason'
    _description = 'Reason for Attendance Lateness'
    _order = 'name'

    name = fields.Char(string="Reason", required=True, translate=True)
    active = fields.Boolean(default=True)
    