# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def get_worked_day_lines(self, contracts, date_from, date_to):
        """
        Override to surface Overtime and Under-Time as dedicated worked-day lines.
        Salary rules can then reference them by code (B_OVERTIME / B_UNDERTIME).
        NOTE: The payslip input type XML records (input_overtime_hours / input_undertime_hours)
        were removed because the overtime model was never implemented.  This version
        uses basic worked_day dict entries only (no payslip input type FK).
        """
        worked_day_lines = super().get_worked_day_lines(contracts, date_from, date_to)

        employee = self.employee_id
        if not employee or not date_from or not date_to:
            return worked_day_lines

        attendances = self.env['hr.attendance'].search([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', date_from),
            ('check_in', '<=', date_to),
        ])

        total_overtime = sum(attendances.mapped('extra_hours'))
        total_undertime = sum(attendances.mapped('under_time_hours'))

        if total_overtime > 0:
            worked_day_lines.append({
                'name': "Overtime Hours (Bank)",
                'code': 'B_OVERTIME',
                'number_of_hours': round(total_overtime, 2),
                'number_of_days': round(total_overtime / 8.0, 2),
                'contract_id': self.contract_id.id if self.contract_id else False,
            })

        if total_undertime < 0:
            worked_day_lines.append({
                'name': "Under Time Hours (Bank)",
                'code': 'B_UNDERTIME',
                'number_of_hours': round(abs(total_undertime), 2),
                'number_of_days': round(abs(total_undertime) / 8.0, 2),
                'contract_id': self.contract_id.id if self.contract_id else False,
            })

        return worked_day_lines