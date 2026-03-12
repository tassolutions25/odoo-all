# -*- coding: utf-8 -*-
from odoo import models, fields

class HrAttendancePolicy(models.Model):
    _name = 'hr.attendance.policy'
    _description = 'Attendance Policy'

    name = fields.Char(string="Policy Name", required=True, help="e.g., Head Office Standard Hours, Branch Hours")
    active = fields.Boolean(default=True)
    
    # Check-in Rules (Req C)
    check_in_earliest = fields.Float(string="Earliest Check-in", default=7.0, help="7.0 for 7:00 AM. Check-ins before this time are ignored.")
    check_in_latest_grace = fields.Float(string="Check-in Grace Period End", default=8.25, help="8.25 for 8:15 AM. Check-ins after this are marked as Late.")
    
    # Check-out Rules (Req C)
    check_out_earliest_grace = fields.Float(string="Earliest Check-out Grace", default=16.92, help="16.92 for 4:55 PM. Check-outs before this are Early Out.")
    check_out_deadline = fields.Float(string="Check-out Deadline", default=18.5, help="18.5 for 12:30 PM. After this, it's a Miss Out.")
    
    resource_calendar_id = fields.Many2one('resource.calendar', string="Working Hours", required=True,
                                           help="The calendar that defines the total scheduled hours for this policy.")