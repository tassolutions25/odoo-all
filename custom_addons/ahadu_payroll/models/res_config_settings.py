# -*- coding: utf-8 -*-
from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    attendance_based_payroll = fields.Boolean(
        string='Attendance Based Payroll',
        config_parameter='ahadu_payroll.attendance_based_payroll',
        help="If checked, payroll calculations will rely on check-in/check-out data. "
             "If unchecked, employees are assumed present unless they have approved leave."
    )
    
    # Overtime Rates
    overtime_rate_normal = fields.Float(string="Normal Rate", config_parameter='ahadu_payroll.ot_rate_normal', default=1.5)
    overtime_rate_night = fields.Float(string="Night Rate", config_parameter='ahadu_payroll.ot_rate_night', default=1.75)
    overtime_rate_weekend = fields.Float(string="Weekend Rate", config_parameter='ahadu_payroll.ot_rate_weekend', default=2.0)
    overtime_rate_holiday = fields.Float(string="Holiday Rate", config_parameter='ahadu_payroll.ot_rate_holiday', default=2.5)

    # Overtime Time Configuration (Boundaries)
    
    # Cash Indemnity
    cash_indemnity_tax_rate = fields.Float(string="Cash Indemnity Tax Rate (%)", config_parameter='ahadu_payroll.cash_indemnity_tax_rate', default=35.0)
