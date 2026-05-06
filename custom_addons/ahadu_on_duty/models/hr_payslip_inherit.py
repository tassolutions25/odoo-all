# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class HrPayslipODInherit(models.Model):
    _inherit = 'hr.payslip'

    def get_worked_day_lines(self, contracts, date_from, date_to):
        """
        Override to ensure On-Duty hours appear as an explicit 'On Duty' line
        in the payslip worked days section (100% counted as worked).

        The OD-generated hr.attendance records already flow through the
        standard attendance→payslip pipeline.  This override ADDS a dedicated
        'OD_HOURS' line so payroll rules can reference it by code if needed.
        """
        worked_day_lines = super().get_worked_day_lines(contracts, date_from, date_to)

        # Derive the employee from the contracts (same employee on all)
        employee = self.employee_id
        if not employee or not date_from or not date_to:
            return worked_day_lines

        # Find approved OD records that overlap the payslip period
        od_records = self.env['hr.on.duty'].search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'approved'),
            ('date_from', '<=', date_to),
            ('date_to', '>=', date_from),
        ])

        if od_records:
            total_od_hours = sum(od_records.mapped('total_hours'))
            total_od_days = 0.0
            for od in od_records:
                if od.od_type == 'full_day':
                    delta = (od.date_to.date() - od.date_from.date()).days + 1
                    total_od_days += delta
                elif od.od_type in ('half_day_am', 'half_day_pm'):
                    delta = (od.date_to.date() - od.date_from.date()).days + 1
                    total_od_days += delta * 0.5
                else:
                    # Hourly: fraction of a working day (8h)
                    total_od_days += od.total_hours / 8.0

            worked_day_lines.append({
                'name': "On Duty Hours",
                'code': 'OD_HOURS',
                'number_of_days': round(total_od_days, 2),
                'number_of_hours': round(total_od_hours, 2),
                'contract_id': self.contract_id.id if self.contract_id else False,
            })

        return worked_day_lines
