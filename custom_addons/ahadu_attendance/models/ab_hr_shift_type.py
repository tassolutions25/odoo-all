# -*- coding: utf-8 -*-
from odoo import models, fields

class AbHrShiftType(models.Model):
    """
    This model acts as a user-friendly layer on top of Odoo's resource.calendar.
    We will manage specific work shifts (like "Morning Shift") as records here,
    making them easy to select and assign.
    """
    _name = 'ab.hr.shift.type'
    _description = 'Ahadu Bank: Shift Type'
    _inherits = {'resource.calendar': 'resource_calendar_id'}

    resource_calendar_id = fields.Many2one(
        'resource.calendar', 
        string='Working Hours', 
        required=True, 
        ondelete='cascade'
    )
    
    # You can add fields specific to a shift type here if needed
    shift_category = fields.Selection([
        ('day', 'Day Shift'),
        ('night', 'Night Shift'),
        ('branch', 'Branch Shift'),
        ('ho', 'Head Office Shift'),
        ('flexible', 'Flexible')
    ], string="Shift Category", default='day',
       help="Categorize shifts for easier filtering and planning.")