# -*- coding: utf-8 -*-
from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    payroll_attendance_mode = fields.Selection([
        ('standard', 'Standard (Assume Full Work)'),
        ('automated', 'Automated (Attendance)'),
        ('manual', 'Manual (Absenteeism Sheets)')
    ], string='Payroll Attendance Mode', 
       config_parameter='ahadu_payroll.payroll_attendance_mode',
       default='standard',
       help="Standard: Presumes employee is present unless leave is approved.\n"
            "Automated: Uses Custome Ahadu Attendance module data.\n"
            "Manual: Uses custom Absenteeism Sheets filled by Officers and approved by Managers.")
    
    # Overtime Rates
    overtime_rate_normal = fields.Float(string="Normal Rate", config_parameter='ahadu_payroll.ot_rate_normal', default=1.5)
    overtime_rate_night = fields.Float(string="Night Rate", config_parameter='ahadu_payroll.ot_rate_night', default=1.75)
    overtime_rate_weekend = fields.Float(string="Weekend Rate", config_parameter='ahadu_payroll.ot_rate_weekend', default=2.0)
    overtime_rate_holiday = fields.Float(string="Holiday Rate", config_parameter='ahadu_payroll.ot_rate_holiday', default=2.5)

    # Overtime Time Configuration (Boundaries)
    
