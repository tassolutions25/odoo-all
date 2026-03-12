# -*- coding: utf-8 -*-
import pytz
import logging
from odoo import models, fields, api, _
from datetime import date, timedelta

class HrEmployee(models.Model):
    _inherit = 'hr.employee'


    hourly_cost = fields.Float(string="Hourly Cost")

    employee_id = fields.Char(string="BioTime Emp ID", help="ID used in BioTime Device", index=True)

    
    # THIS IS THE CORRECT LOCATION FOR THE FIELD DEFINITION
    attendance_policy_id = fields.Many2one(
        'hr.attendance.policy', 
        string="Attendance Policy",
        help="The attendance policy currently assigned to this employee.",
        company_dependent=True,
        copy=False
    )
    # biotime_sync_date = fields.Datetime(string="Last BioTime Sync", readonly=True, copy=False)
    biotime_sync_date = fields.Datetime(string="Last BioTime Sync", readonly=True)

    shift_schedule_ids = fields.One2many(
        'ab.hr.shift.schedule',
        'employee_id',
        string='Shift Schedule'
    )


     
     # --- THIS IS THE DEFINITIVE FIX FOR THE VALIDATION ERROR ---
    def _attendance_action_change(self, geo_ip_response=None):
        """
        This is the definitive override for the check-in/out action.
        It correctly handles Miss-Outs from previous days and Miss-Ins.
        """
        self.ensure_one()
        action_date = fields.Datetime.now()
        
        # Find the last attendance record for this employee that has no check-out
        open_attendance = self.env['hr.attendance'].search([
            ('employee_id', '=', self.id),
            ('check_out', '=', False)
        ], limit=1)

        if open_attendance:
            # --- An open attendance exists ---
            if open_attendance.check_in.date() < action_date.date():
                # This is a "stuck" check-in. Mark it as Miss-Out.
                open_attendance.write({'attendance_status': 'miss_out'})
                # Create a NEW check-in for the current action
                self.env['hr.attendance'].create({
                    'employee_id': self.id,
                    'check_in': action_date,
                })
            else:
                # This is a normal check-out for the CURRENT day
                open_attendance.write({'check_out': action_date})
        else:
            # --- No open attendance, so this is a new check-in ---
            self.env['hr.attendance'].create({
                'employee_id': self.id,
                'check_in': action_date,
            })
        
        # return self.env['ir.actions.act_window']._for_xml_id('hr_attendance.hr_attendance_action_from_systray')
        return {
            'type': 'ir.actions.act_window',
            'name': 'My Attendances',
            'res_model': 'hr.attendance',
            'view_mode': 'tree,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }
            
    # The methods are defined after the fields
    def _check_unplanned_absences_and_warnings(self):
        """
        Scheduled action to detect unplanned absences and generate warnings.
        """
        yesterday = fields.Date.context_today(self) - timedelta(days=1)
        # The method should operate on a recordset, so we get all employees here
        employees_to_check = self.env['hr.employee'].search([('active', '=', True)])

        for emp in employees_to_check:
            # --- 1. Check for Assigned Shift ---
            shift = self.env['ab.hr.shift.schedule'].search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'assigned'),
                ('date_start', '<=', datetime.combine(yesterday, time(23, 59))),
                ('date_end', '>=', datetime.combine(yesterday, time(0, 0)))
            ], limit=1)
            
            should_check = False
            check_in_start = False
            check_in_end = False
            
            if shift:
                should_check = True
                # Use shift times (with buffer?)
                # If shift crosses midnight, it's tricky, but let's assume single day for now as per Ahadu
                check_in_start = shift.date_start - timedelta(hours=4) # Early checkin allowed
                check_in_end = shift.date_end + timedelta(hours=4)     # Late checkout allowed
            elif emp.resource_calendar_id:
                # Fallback to standard calendar
                day_start = fields.Datetime.to_datetime(yesterday)
                day_end = day_start + timedelta(days=1)
                intervals_dict = emp.resource_calendar_id._work_intervals_batch(
                    day_start, day_end,
                    resources=emp.resource_id
                )
                work_intervals = list(intervals_dict.get(emp.resource_id.id, []))
                if work_intervals:
                    should_check = True
                    check_in_start = day_start
                    check_in_end = day_end

            if not should_check:
                continue
                
            # Did they check in within the window?
            if self.env['hr.attendance'].search_count([
                ('employee_id', '=', emp.id), 
                ('check_in', '>=', check_in_start), 
                ('check_in', '<', check_in_end)
            ]):
                continue
            
            # Were they on leave or duty?
            if self.env['hr.leave'].search_count([('employee_id', '=', emp.id), ('state', '=', 'validate'), ('date_from', '<=', yesterday), ('date_to', '>=', yesterday)]):
                continue
            if self.env['ab.hr.duty.request'].search_count([('employee_id', '=', emp.id), ('state', '=', 'approved'), ('date_from', '<=', yesterday), ('date_to', '>=', yesterday)]):
                continue
            
            # Have we already logged this absence?
            if self.env['ab.hr.unplanned.absence'].search_count([('employee_id', '=', emp.id), ('date', '=', yesterday)]):
                continue

            # Log the unplanned absence and notify manager
            absence = self.env['ab.hr.unplanned.absence'].create({'employee_id': emp.id, 'date': yesterday})
            if emp.parent_id.user_id:
                absence.activity_schedule('mail.mail_activity_data_todo', summary=_("Review Unplanned Absence"), user_id=emp.parent_id.user_id.id)
        
        # --- Generate Recurring Warnings ---
        one_week_ago = fields.Date.context_today(self) - timedelta(days=7)
        late_employees = self.env['hr.attendance'].read_group(
            domain=[('is_late', '=', True), ('check_in', '>=', one_week_ago)],
            fields=['employee_id'], groupby=['employee_id']
        )
        for group in late_employees:
            if group['employee_id_count'] >= 3:
                employee = self.env['hr.employee'].browse(group['employee_id'][0])
                if not self.env['ab.hr.disciplinary.note'].search_count([('employee_id', '=', employee.id), ('reason_type', '=', 'lateness'), ('create_date', '>=', one_week_ago)]):
                    note = self.env['ab.hr.disciplinary.note'].create({
                        'employee_id': employee.id,
                        'reason_type': 'lateness',
                        'details': f"Employee was late {group['employee_id_count']} times in the last 7 days."
                    })
                    note.action_send_note()

    def _update_employee_calendars_from_roster(self):
        """
        Update employee calendars based on their shift roster schedules.
        This method is called by a scheduled action to sync shift assignments with employee calendars.
        """
        _logger = logging.getLogger(__name__)
        for employee in self:
            try:
                # Find active shift schedules for this employee
                today = fields.Date.context_today(self)
                shift_schedules = self.env['ab.hr.shift.schedule'].search([
                    ('employee_id', '=', employee.id),
                    ('date', '=', today),
                    ('state', '=', 'assigned')
                ])
                
                if shift_schedules:
                    # Get the shift's resource calendar
                    shift_type = shift_schedules[0].shift_type_id
                    if shift_type and shift_type.resource_calendar_id:
                        # Update employee's calendar to match the shift
                        employee.resource_calendar_id = shift_type.resource_calendar_id
                        _logger.info(f"Updated calendar for employee {employee.name} based on shift roster")
            except Exception as e:
                _logger.error(f"Error updating calendar for employee {employee.id}: {e}")
        return True