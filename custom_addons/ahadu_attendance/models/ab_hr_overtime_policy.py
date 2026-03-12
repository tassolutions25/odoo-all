# -*- coding: utf-8 -*-
from odoo import models, fields

class AbHrOvertimePolicy(models.Model):
    _name = 'ab.hr.overtime.policy'
    _description = 'Overtime Rate Policy'
    _order = 'sequence'

    name = fields.Char(string="Policy Name", required=True, help="e.g., Standard Weekday, Public Holiday")
    sequence = fields.Integer(default=10)
    rate_multiplier = fields.Float(string="Rate Multiplier", required=True, default=1.5,
                                   help="e.g., 1.5 for Time and a Half, 2.0 for Double Time")
    day_type = fields.Selection([
        ('weekday', 'Weekday'),
        ('saturday', 'Saturday'),
        ('sunday', 'Sunday'),
        ('holiday', 'Public Holiday'),
    ], string="Applicable Day Type", required=True, default='weekday')
    active = fields.Boolean(default=True)