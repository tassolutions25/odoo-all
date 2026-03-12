# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta
import pytz


# ===================================================================
#  1. DEFINE THE LINE MODEL FIRST
# ===================================================================
class AbHrOvertimeRequestLine(models.Model):
    _name = 'ab.hr.overtime.request.line'
    _description = 'Overtime Request Attendance Line'

    overtime_request_id = fields.Many2one('ab.hr.overtime.request', string="Overtime Request", ondelete='cascade')
    attendance_id = fields.Many2one('hr.attendance', string="Attendance Record", required=True, readonly=True)
    
    # Related fields for easy display in the view
    check_in = fields.Datetime(related='attendance_id.check_in', readonly=True)
    check_out = fields.Datetime(related='attendance_id.check_out', readonly=True)
    worked_hours = fields.Float(related='attendance_id.worked_hours', readonly=True)
    # extra_hours = fields.Float(related='attendance_id.extra_hours', readonly=True, string="Overtime")
    calculated_extra_hours = fields.Float(
        string="Overtime", 
        compute='_compute_calculated_extra_hours'
    )


    @api.depends('attendance_id.worked_hours', 'attendance_id.employee_id.resource_calendar_id')
    def _compute_calculated_extra_hours(self):
        for line in self:
            att = line.attendance_id
            if not att or not att.check_out or not att.employee_id.resource_calendar_id:
                line.calculated_extra_hours = 0.0
                continue

            calendar = att.employee_id.resource_calendar_id
            tz = pytz.timezone(att.employee_id.tz or self.env.user.tz or 'UTC')
            
            # Localize attendance times to use in resource calculation
            check_in_loc = pytz.utc.localize(att.check_in).astimezone(tz)
            check_out_loc = pytz.utc.localize(att.check_out).astimezone(tz)
            
            # Calculate overlapping working hours during this specific attendance
            # We pass the attendance duration as the range to _work_intervals_batch
            intervals_dict = calendar._work_intervals_batch(
                check_in_loc,
                check_out_loc,
                resources=att.employee_id.resource_id,
                tz=tz
            )
            work_intervals = list(intervals_dict.get(att.employee_id.resource_id.id, []))
            
            # Sum up the duration of working time within this attendance
            scheduled_seconds = sum((i[1] - i[0]).total_seconds() for i in work_intervals)
            worked_seconds = (att.check_out - att.check_in).total_seconds()
            
            # Overtime is the time worked that WASN'T scheduled
            # i.e., Duration - IntersectingSchedule
            extra_seconds = worked_seconds - scheduled_seconds
            
            line.calculated_extra_hours = max(0.0, round(extra_seconds / 3600, 2))

    def action_open_attendance_form(self):
        """
        This method is called from the button on the line.
        It opens the full form view of the related hr.attendance record.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.attendance',
            'res_id': self.attendance_id.id,
            'view_mode': 'form',
            'target': 'new',
        }


class AbHrOvertimeRequest(models.Model):
    _name = 'ab.hr.overtime.request'
    _description = 'Employee Overtime Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'overtime_date desc'

    _sql_constraints = [
        ('employee_date_uniq', 'unique(employee_id, overtime_date)', 
         'An overtime request for this employee on this date already exists!')
    ]

    name = fields.Char(string="Request Title", required=True, readonly=True, states={'draft': [('readonly', False)]}, default="Overtime Request")
    employee_id = fields.Many2one('hr.employee', string="Employee", required=True, default=lambda self: self.env.user.employee_id, readonly=True, states={'draft': [('readonly', False)]})
    overtime_date = fields.Date(string="Overtime Date", required=True, default=fields.Date.context_today, readonly=True, states={'draft': [('readonly', False)]})
    
    actual_worked_hours = fields.Float(string="Actual Worked Hours", compute='_compute_attendance_data', store=True)
    scheduled_hours = fields.Float(string="Scheduled Hours", compute='_compute_attendance_data', store=True)
    duration = fields.Float(string="Calculated Overtime (Hours)", compute='_compute_attendance_data', store=True)
    
    payable_hours = fields.Float(string="Payable Hours", readonly=True, states={'to_approve': [('readonly', False)]})
    
    overtime_policy_id = fields.Many2one('ab.hr.overtime.policy', string="Overtime Policy", compute='_compute_attendance_data', store=True,
                                         help="The overtime policy automatically determined for this day.")

    reason = fields.Text(string="Reason", required=True, readonly=True, states={'draft': [('readonly', False)]})
    manager_id = fields.Many2one(related='employee_id.parent_id', string="Manager", store=True)
    state = fields.Selection([
        ('draft', 'Draft'), ('to_approve', 'To Approve'),
        ('approved', 'Approved'), ('rejected', 'Rejected')
    ], string="Status", default='draft', tracking=True)
   
    # check_in = fields.Datetime(string="Check In", related='attendance_id.check_in', readonly=True, store=True)
    # check_out = fields.Datetime(string="Check Out", related='attendance_id.check_out', readonly=True, store=True)
    # worked_hours = fields.Float(string="Worked Hours", related='attendance_id.worked_hours', readonly=True, store=True)
    # extra_hours = fields.Float(string="Overtime", related='attendance_id.extra_hours', readonly=True, store=True)

    line_ids = fields.One2many('ab.hr.overtime.request.line', 'overtime_request_id', string="Related Attendances")

    @api.constrains('employee_id', 'overtime_date')
    def _check_unique_overtime_request(self):
        for request in self:
            if self.search_count([
                ('id', '!=', request.id),
                ('employee_id', '=', request.employee_id.id),
                ('overtime_date', '=', request.overtime_date),
            ]) > 0:
                raise ValidationError(_("You cannot create more than one overtime request for the same employee on the same day."))
    
    @api.depends('employee_id', 'overtime_date')
    def _compute_attendance_data(self):
        for request in self:
            # --- 1. Reset all values ---
            if not request.employee_id or not request.overtime_date:
                request.update({
                    'actual_worked_hours': 0.0,
                    'scheduled_hours': 0.0,
                    'duration': 0.0,
                    'line_ids': [(5, 0, 0)], # Command to clear all existing lines
                    'overtime_policy_id': False,
                })
                continue
                
            # --- 2. Find relevant attendance records ---
            day_start_utc = fields.Datetime.to_datetime(request.overtime_date)
            day_end_utc = day_start_utc + timedelta(days=1)
            attendances = self.env['hr.attendance'].search([
                ('employee_id', '=', request.employee_id.id),
                ('check_in', '>=', day_start_utc),
                ('check_in', '<', day_end_utc),
                ('check_out', '!=', False)
            ])
            
            # --- 3. If no attendances, clear fields and stop ---
            if not attendances:
                request.update({
                    'actual_worked_hours': 0.0,
                    'scheduled_hours': 0.0,
                    'duration': 0.0,
                    'line_ids': [(5, 0, 0)],
                    'overtime_policy_id': False,
                })
                continue

            # --- 4. Recompute source data and prepare lines ---
            # This ensures the 'extra_hours' on the attendance records is up-to-date
            attendances._recompute_overtime_and_undertime()
            
            # Prepare the commands to create the new lines for the One2many field
            lines_to_create = [(0, 0, {'attendance_id': att.id}) for att in attendances]

            # --- 5. Calculate Scheduled Hours ---
            calendar = request.employee_id.resource_calendar_id
            scheduled_hours = 0.0
            if calendar:
                tz = pytz.timezone(request.employee_id.tz or self.env.user.tz or 'UTC')
                intervals_dict = calendar._work_intervals_batch(
                    day_start_utc.astimezone(pytz.utc),
                    day_end_utc.astimezone(pytz.utc),
                    resources=request.employee_id.resource_id,
                    tz=tz
                )
                work_intervals = list(intervals_dict.get(request.employee_id.resource_id.id, []))
                scheduled_hours = sum((i[1] - i[0]).total_seconds() / 3600 for i in work_intervals)

            # --- 6. Calculate Totals ---
            # Bank Policy: Overtime is worked_hours - scheduled_hours
            # We strictly use scheduled_hours from the calendar (which handles Sat/Sun/Holidays).
            # If no schedule (e.g. Holiday or Day Off), basic hours is 0, so all worked is OT.
            
            actual_worked_hours = sum(attendances.mapped('worked_hours'))
            
            # Use scheduled hours as baseline (Sat: 4h, Mon-Fri: 8h)
            baseline_hours = scheduled_hours
            
            # Calculate duration (raw overtime hours)
            duration = round(actual_worked_hours - baseline_hours, 2) if actual_worked_hours > baseline_hours else 0.0
            
            # --- 7. Determine Policy ---
            day_of_week = request.overtime_date.weekday()
            day_type = 'weekday'
            if day_of_week == 5: day_type = 'saturday'
            elif day_of_week == 6: day_type = 'sunday'
            
            # Check for Public Holiday? (Would need hr.public.holiday module or similar, skipping for now)
            
            policy = self.env['ab.hr.overtime.policy'].search([('day_type', '=', day_type), ('active', '=', True)], limit=1)
            
            # --- 8. Update all fields on the request at once ---
            request.update({
                'line_ids': [(5, 0, 0)] + lines_to_create, # Clear old lines and add new ones
                'actual_worked_hours': actual_worked_hours,
                'scheduled_hours': scheduled_hours,
                'duration': duration,
                'overtime_policy_id': policy.id,
            })

    def action_submit(self):
        self.ensure_one()
        if self.duration <= 0:
            raise ValidationError(_("There is no calculated overtime for the selected date. This request cannot be submitted."))
        
        # Apply Rate Multiplier to Payable Hours
        multiplier = self.overtime_policy_id.rate_multiplier if self.overtime_policy_id else 1.0
        self.payable_hours = self.duration * multiplier
        
        self.write({'state': 'to_approve'})
        if self.manager_id.user_id:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_("Approve Overtime Request: %s") % self.name,
                user_id=self.manager_id.user_id.id
            )
         # Send email to manager
        template = self.env.ref('ahadu_attendance.email_template_overtime_to_approve', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)

    def action_approve(self):
        self.ensure_one()
        if self.payable_hours <= 0:
            raise ValidationError(_("Payable Hours must be greater than zero to approve."))
        
        attendances_to_update = self.line_ids.mapped('attendance_id')
        if attendances_to_update:
            attendances_to_update.write({'overtime_request_id': self.id})
            
        self.activity_feedback(['mail.mail_activity_data_todo'])
        self.write({'state': 'approved'})
        self.message_post(body=_("Overtime request has been approved by %s.") % self.env.user.name)

         # Send email to employee
        template = self.env.ref('ahadu_attendance.email_template_overtime_status_change', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)

    def action_reject(self):
        self.activity_feedback(['mail.mail_activity_data_todo'])
        self.write({'state': 'rejected'})

         # Send email to employee
        template = self.env.ref('ahadu_attendance.email_template_overtime_status_change', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)

    def action_to_draft(self):
        self.write({'state': 'draft'})

