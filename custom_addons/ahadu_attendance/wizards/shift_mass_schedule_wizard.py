# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging
from odoo.exceptions import UserError
from datetime import datetime, time, timedelta

_logger = logging.getLogger(__name__)


class ShiftMassScheduleWizard(models.TransientModel):
    _name = 'shift.mass.schedule.wizard'
    _description = 'Wizard to Schedule Shifts in Mass'

    shift_type_id = fields.Many2one(
        'ab.hr.shift.type', 
        string="Shift Type to Assign", 
        required=True
    )
    date_from = fields.Date(string="Date", required=True, default=fields.Date.context_today)
    
    # Target employees by departments, tags, or individually
    department_ids = fields.Many2many('hr.department', string="Departments")
    employee_tag_id = fields.Many2one('hr.employee.category', string="Employee Tag")
    employee_ids = fields.Many2many('hr.employee', string="Specific Employees")

    @api.onchange('department_ids', 'employee_tag_id')
    def _onchange_filter(self):
        # Helper to show which employees will be affected
        domain = []
        if self.department_ids:
            domain.append(('department_id', 'in', self.department_ids.ids))
        if self.employee_tag_id:
            domain.append(('category_ids', 'in', self.employee_tag_id.id))
        
        if domain:
            employees = self.env['hr.employee'].search(domain)
            self.employee_ids = [(6, 0, employees.ids)]
        # Else: Do not clear if user manually selected employees

    def action_generate_shifts(self):
        if not self.employee_ids:
            raise UserError(_("You must select at least one employee to schedule."))

        calendar = self.shift_type_id.resource_calendar_id
        if not calendar:
            raise UserError(_("The selected shift type does not have a defined working calendar."))

        _logger.info(
            "Mass Shift Wizard: Shift Type='%s', Calendar='%s' (ID=%s), Employees=%d",
            self.shift_type_id.name, calendar.name, calendar.id, len(self.employee_ids)
        )

        # =====================================================================
        # Step 1: Update Employee + Contract Calendars to match Shift Type
        # =====================================================================
        calendar_updated_count = 0
        contract_updated_count = 0

        for employee in self.employee_ids:
            # Update Employee's Working Hours
            if employee.resource_calendar_id.id != calendar.id:
                _logger.info(
                    "  Updating Employee '%s': calendar %s -> %s",
                    employee.name, employee.resource_calendar_id.id, calendar.id
                )
                employee.write({'resource_calendar_id': calendar.id})
                calendar_updated_count += 1

            # Update the Employee's active Contract
            contracts = self.env['hr.contract'].search([
                ('employee_id', '=', employee.id),
                ('state', 'in', ['open', 'close', 'draft'])
            ], order='state asc, date_start desc', limit=1)

            if contracts and contracts.resource_calendar_id.id != calendar.id:
                _logger.info(
                    "  Updating Contract '%s' for '%s': calendar %s -> %s",
                    contracts.name, employee.name,
                    contracts.resource_calendar_id.id, calendar.id
                )
                contracts.write({'resource_calendar_id': calendar.id})
                contract_updated_count += 1

        _logger.info(
            "Mass Shift Wizard: Updated %d employee calendars, %d contract calendars",
            calendar_updated_count, contract_updated_count
        )

        # =====================================================================
        # Step 2: Generate Shift Schedule Records (Single Date)
        # =====================================================================
        vals_list = []
        current_date = self.date_from
        
        day_of_week = current_date.weekday()  # 0=Mon
        
        attendances = calendar.attendance_ids.filtered(
            lambda a: int(a.dayofweek) == day_of_week and a.day_period != 'lunch'
        )
        
        if attendances:
            start_hour = min(attendances.mapped('hour_from'))
            end_hour = max(attendances.mapped('hour_to'))
            
            def float_to_time(val):
                hour = int(val)
                minute = int(round((val - hour) * 60))
                if minute == 60:
                    minute = 0
                    hour += 1
                if hour >= 24:
                    hour = 0
                return time(hour, minute)

            start_dt = datetime.combine(current_date, float_to_time(start_hour))
            end_dt = datetime.combine(current_date, float_to_time(end_hour))
            
            existing_shifts = self.env['ab.hr.shift.schedule'].search([
                ('employee_id', 'in', self.employee_ids.ids),
                ('date_start', '=', start_dt)
            ])
            existing_map = {(s.employee_id.id, s.date_start): True for s in existing_shifts}

            for employee in self.employee_ids:
                if (employee.id, start_dt) in existing_map:
                    continue

                vals_list.append({
                    'employee_id': employee.id,
                    'shift_type_id': self.shift_type_id.id,
                    'department_id': employee.department_id.id,
                    'date_start': start_dt,
                    'date_end': end_dt,
                    'state': 'assigned',
                })
        
        if vals_list:
            self.env['ab.hr.shift.schedule'].create(vals_list)
        
        msg_parts = []
        if vals_list:
            msg_parts.append(_("Generated %s shift records for %s.") % (len(vals_list), current_date))
        else:
            msg_parts.append(_("No new shifts generated for %s.") % current_date)
        
        if calendar_updated_count:
            msg_parts.append(_("Updated Working Hours for %s employees.") % calendar_updated_count)
        if contract_updated_count:
            msg_parts.append(_("Updated Working Schedule for %s contracts.") % contract_updated_count)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Shifts Generated"),
                'message': " ".join(msg_parts),
                'type': 'success',
                'sticky': False,
            }
        }