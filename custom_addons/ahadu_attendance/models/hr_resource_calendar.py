# -*- coding: utf-8 -*-
from odoo import models, fields

class ResourceCalendar(models.Model):
    _inherit = 'resource.calendar'

    # The field for Shift Management
    shift_category = fields.Selection([
        ('day', 'Day Shift'),
        ('night', 'Night Shift'),
        ('branch', 'Branch Shift'),
        ('ho', 'Head Office Shift'),
        ('flexible', 'Flexible')
    ], string="Shift Category", default='day')

    # The field for Lateness Tolerance
    tolerance_late_check_in = fields.Float(
        string="Late Check-in Tolerance (Minutes)", 
        default=15.0, 
        help="Allowed delay in minutes before an employee is marked as late."
    )

