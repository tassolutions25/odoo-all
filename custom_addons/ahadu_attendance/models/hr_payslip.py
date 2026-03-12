# -*- coding: utf-8 -*-
from odoo import models, fields, api

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    @api.model
    def _get_worked_day_lines(self, employee, date_from, date_to):
        """
        Override to inject Overtime and Under Time as inputs.
        """
        worked_day_lines = super()._get_worked_day_lines(employee, date_from, date_to)
        
        # Calculate total overtime and under time for the payslip period
        attendances = self.env['hr.attendance'].search([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', date_from),
            ('check_in', '<=', date_to),
        ])
        
        total_overtime = sum(attendances.mapped('extra_hours'))
        total_undertime = sum(attendances.mapped('under_time_hours'))
        
        # Inject as inputs
        if total_overtime > 0:
            worked_day_lines.append({
                'name': "Overtime Hours (Bank)",
                'code': 'B_OVERTIME',
                'payslip_input_type_id': self.env.ref('ahadu_attendance.input_overtime_hours').id,
                'amount': total_overtime,
                'contract_id': self.contract_id.id,
            })
            
        if total_undertime < 0:
            worked_day_lines.append({
                'name': "Under Time Hours (Bank)",
                'code': 'B_UNDERTIME',
                'payslip_input_type_id': self.env.ref('ahadu_attendance.input_undertime_hours').id,
                'amount': total_undertime,
                'contract_id': self.contract_id.id,
            })
            
        return worked_day_lines