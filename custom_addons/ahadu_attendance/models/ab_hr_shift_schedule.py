# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, time

class AbHrShiftSchedule(models.Model):
    _name = 'ab.hr.shift.schedule'
    _description = 'Ahadu Bank: Employee Shift Schedule'
    _order = 'date_start'

    name = fields.Char(compute='_compute_name', store=True)
    employee_id = fields.Many2one(
        'hr.employee', 
        string="Employee", 
        required=True)
    department_id = fields.Many2one(
        'hr.department', 
        string="Department", 
        related='employee_id.department_id', 
        store=True
        )
    shift_type_id = fields.Many2one(
        'ab.hr.shift.type', 
        string="Shift Type", 
        required=True
        )
    
      # Dates for planning
    date_start = fields.Datetime(
        string="Start Date & Time",
        required=True
    )
    date_end = fields.Datetime(
        string="End Date & Time",
        required=True
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('assigned', 'Assigned'),
        ('cancelled', 'Cancelled')
    ], string="Status", default='draft', tracking=True)
    
    color = fields.Integer(string="Color Index")  # Used for Calendar color coding
    
    # For Gantt compatibility (can also be used by Calendar)
    start_datetime = fields.Datetime(compute='_compute_datetimes', store=True)
    stop_datetime = fields.Datetime(compute='_compute_datetimes', store=True)

    @api.depends('employee_id', 'shift_type_id', 'date_start')
    def _compute_name(self):
        for schedule in self:
            if schedule.employee_id and schedule.shift_type_id and schedule.date_start:
                schedule.name = (
                    f"{schedule.employee_id.name} - "
                    f"{schedule.shift_type_id.name} "
                    f"on {schedule.date_start.strftime('%Y-%m-%d %H:%M')}"
                )
            else:
                schedule.name = "Shift"

    @api.depends('date_start', 'date_end')
    def _compute_datetimes(self):
        for schedule in self:
            if schedule.date_start:
                schedule.start_datetime = datetime.combine(schedule.date_start, time.min)
            else:
                schedule.start_datetime = False

            if schedule.date_end:
                schedule.stop_datetime = datetime.combine(schedule.date_end, time.max)
            else:
                schedule.stop_datetime = False

    def action_shift_assign(self):
        """Change state to assigned."""
        for schedule in self:
             # Basic validation?
             schedule.write({'state': 'assigned'})
    
    def action_shift_cancel(self):
        """Change state to cancelled."""
        self.write({'state': 'cancelled'})
        
    def action_shift_reset_draft(self):
        """Reset state to draft."""
        self.write({'state': 'draft'})

     # Optional: helper actions to jump between views
    def action_open_calendar_view(self):
        """Open this model in Calendar view."""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Shift Schedule (Calendar)',
            'res_model': 'ab.hr.shift.schedule',
            'view_mode': 'calendar,tree,form',
            'target': 'current',
        }
    def action_open_gantt_view(self):
        """Open this model in Gantt view."""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Shift Schedule (Gantt)',
            'res_model': 'ab.hr.shift.schedule',
            'view_mode': 'gantt,tree,form',
            'target': 'current',
        }
