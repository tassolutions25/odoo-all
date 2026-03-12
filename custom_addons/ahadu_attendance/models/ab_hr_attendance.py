# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _, exceptions
from odoo.exceptions import UserError, ValidationError
from datetime import date, datetime, time, timedelta
import pytz
try:
    from odoo.addons.ahadu_hr_leave.models.ethiopian_calendar import EthiopianDateConverter
except ImportError:
    EthiopianDateConverter = None

_logger = logging.getLogger(__name__)

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    # ===================================================================
    #  1. FIELD DEFINITIONS
    # ===================================================================

    # --- Custom Tracking & Linking Fields ---
    check_in_method = fields.Selection([
        ('Biometric', 'Biometric'), ('PC', 'Computer Device'), ('Mobile', 'Smartphone'),
        ('Card', 'ID Card'), ('Manual', 'Manual Entry'), ('System', 'System Generated')
    ], string="Check-in Method", default='Manual', readonly=True)

    # Add this field to prevent duplicates
    biotime_punch_id = fields.Integer(string="BioTime Punch ID", readonly=True, copy=False, index=True)
    employee_emp_code = fields.Char(
    related='employee_id.employee_id',  # or employee_id.emp_code depending on your HR model
    string='Emp ID',
    store=False )

    department_id = fields.Many2one(
        related='employee_id.department_id',
        string='Department',
        store=False,
        readonly=True
    )

    
    device_mac_address = fields.Char(string="Device MAC Address", readonly=True)
    check_in_gps = fields.Char(string="Check-in Geolocation", readonly=True)
    check_out_gps = fields.Char(string="Check-out Geolocation", readonly=True)
    attendance_sheet_id = fields.Many2one('ab.hr.attendance.sheet', string="Attendance Sheet", ondelete='cascade')
    overtime_request_id = fields.Many2one('ab.hr.overtime.request', string="Overtime Request", readonly=True, copy=False)
    
    is_late = fields.Boolean(string="Is Late", compute="_compute_attendance_analysis", store=True)
    is_early = fields.Boolean(string="Is Early", compute="_compute_is_early", store=True)
    late_minutes = fields.Float(string="Late Minutes", compute="_compute_attendance_analysis", store=True)
    early_minutes = fields.Float(string="Early Minutes", compute="_compute_early_minutes", store=True) # Keeping for legacy if needed, but primary is below
    
    late_duration_display = fields.Char(
    string="Late Duration Display", 
    compute="_compute_attendance_analysis",
    store=True)
    late_display = fields.Char(string="Late Display", compute="_compute_attendance_analysis", store=True)    # Mapped to same logic

    
    early_out_minutes = fields.Float(string="Early Out (Minutes)", compute='_compute_attendance_analysis', store=True)
    early_out_duration_display = fields.Char(string="Early Out Duration", compute='_compute_attendance_analysis', store=True)
    # --- New fields for Lunch & Enhanced Status ---
    lunch_out = fields.Datetime(string="Lunch Out")
    lunch_in = fields.Datetime(string="Lunch In")

    attendance_status = fields.Selection([
        ('on_time', 'On-Time'),
        ('late_in', 'Late-In'),
        ('early_out', 'Early-Out'),
        ('miss_out', 'Miss-Out'),
        ('miss_in', 'Miss-In'), # For future use if needed
        ('late_in_early_out', 'Late-In & Early-Out'),
        ('late_in_miss_out', 'Late-In & Miss-Out'),
        ('early_out_miss_in', 'Early-Out & Miss-In'), # For future use if needed
        ('on_time_miss_out', 'On-Time & Miss-Out'), # Added for when check-in is on-time but check-out is missed
    ], string="Status", compute='_compute_attendance_analysis', store=True)
    
    # Flag to track if a miss-out has been system-handled to allow next day check-in
    # This prevents the default Odoo validation error for open attendances.
    miss_out_status_handled = fields.Boolean(string="Miss-Out Handled", default=False,
                                             help="True if this attendance was marked as Miss-Out by the system "
                                                  "to allow a new check-in the next day.")

    # A field to indicate the type of punch action
    punch_type = fields.Selection([
        ('check_in', 'Check In'),
        ('check_out', 'Check Out'),
        ('lunch_out', 'Lunch Out'),
        ('lunch_in', 'Lunch In'),
    ], string="Punch Type", readonly=True)


    # --- Fields for Lateness Reasons ---
    lateness_reason_id = fields.Many2one('ab.hr.attendance.lateness.reason', string="Lateness Reason")
    lateness_comment = fields.Text(string="Lateness Comment")

    # --- Manually Calculated Fields for Overtime/Under Time ---
    extra_hours = fields.Float(string="Overtime", store=True, readonly=True, help="Positive extra hours worked compared to the schedule.")
    under_time_hours = fields.Float(string="Under Time", store=True, readonly=True, help="Negative hours (worked less than scheduled).")

    # ✅ ADDED: check_out_method was being written to but not declared
    check_out_method = fields.Selection([
        ('Biometric', 'Biometric'), ('PC', 'Computer Device'), ('Mobile', 'Smartphone'),
        ('Card', 'ID Card'), ('Manual', 'Manual Entry'), ('System', 'System Generated')
    ], string="Check-out Method", default='Manual', readonly=False)  # not readonly because we write it in code
    
    # --- Leave Integration Fields ---
    leave_id = fields.Many2one('hr.leave', string="Related Leave", readonly=True, copy=False)
    leave_type_id = fields.Many2one('hr.leave.type', string="Leave Type", readonly=True, copy=False)
    is_on_leave = fields.Boolean(string="On Leave", readonly=True, default=False, copy=False)
    leave_status_code = fields.Char(string="Leave Status Code", readonly=True, copy=False,
                                     help="Short code for leave type (e.g., 'SL' for Sick Leave, 'AL' for Annual Leave)")



    # ===================================================================
    #  2. COMPUTE METHODS
    # ===================================================================
    
    # def _get_employee_tz(self):
    #     self.ensure_one()
    #     try:
    #         return pytz.timezone(self.employee_id.tz or self.env.user.tz or 'UTC')
    #     except pytz.UnknownTimeZoneError:
    #         _logger.warning(f"Unknown timezone for employee {self.employee_id.name} or user. Falling back to UTC.")
    #         return pytz.utc

    def _get_employee_tz(self):
        """
        ✅ FIXED: Safe timezone retrieval that doesn't rely on ensure_one()
        Returns a pytz timezone object for the attendance record's employee, falling back to user tz or UTC.
        """
        # If self is an attendance record with employee info, prefer that
        try:
            # prefer employee's timezone if available
            if self and len(self) == 1 and getattr(self, 'employee_id', False):
                tz_name = self.employee_id.tz or self.env.user.tz or 'UTC'
            else:
                tz_name = self.env.user.tz or 'UTC'
            return pytz.timezone(tz_name)
        except Exception as e:
            _logger.warning("Unable to determine timezone (%s). Falling back to UTC. Error: %s", tz_name, e)
            return pytz.utc

        
    @api.depends('check_in')
    def _compute_late_minutes(self):
        for rec in self:
            rec.late_minutes = 0.0
            if rec.check_in:
                # check_in is stored as UTC datetime; compute using date portion (naive comparison is OK here)
                try:
                    standard_in_end = datetime.combine(rec.check_in.date(), time(8, 15))
                except Exception:
                    standard_in_end = None
                if standard_in_end and rec.check_in > standard_in_end:
                    delta = rec.check_in - standard_in_end
                    rec.late_minutes = round(delta.total_seconds() / 60.0, 2)

    @api.depends('check_out')
    def _compute_early_minutes(self):
        for rec in self:
            rec.early_minutes = 0.0
            if rec.check_out:
                try:
                    standard_out = datetime.combine(rec.check_out.date(), time(16, 55))
                except Exception:
                    standard_out = None
                if standard_out and rec.check_out < standard_out:
                    delta = standard_out - rec.check_out
                    rec.early_minutes = round(delta.total_seconds() / 60.0, 2)

    @api.depends('check_in')
    def _compute_is_late(self):
        for rec in self:
            rec.is_late = False
            if rec.check_in:
                try:
                    allowed_checkin_end = datetime.combine(rec.check_in.date(), time(8, 15))
                except Exception:
                    allowed_checkin_end = None
                if allowed_checkin_end and rec.check_in > allowed_checkin_end:
                    rec.is_late = True

    @api.depends('check_out')
    def _compute_is_early(self):
        for rec in self:
            rec.is_early = False
            if rec.check_out:
                try:
                    allowed_checkout_start = datetime.combine(rec.check_out.date(), time(16, 55))
                except Exception:
                    allowed_checkout_start = None
                if allowed_checkout_start and rec.check_out < allowed_checkout_start:
                    rec.is_early = True

    # Combined into _compute_attendance_analysis
    
    def _update_leave_status(self):
        """
        Update leave status for the attendance date.
        Check if employee has approved leave on the attendance date.
        Can be called manually when needed.
        """
        for rec in self:
            rec.leave_id = False
            rec.leave_type_id = False
            rec.is_on_leave = False
            rec.leave_status_code = False
            
            if not rec.employee_id or not rec.check_in:
                continue
            
            try:
                attendance_date = rec.check_in.date()
                
                # Search for approved leaves that cover this date
                leaves = self.env['hr.leave'].search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('state', '=', 'validate'),
                    ('request_date_from', '<=', attendance_date),
                    ('request_date_to', '>=', attendance_date),
                ], limit=1)
                
                if leaves:
                    leave = leaves[0]
                    rec.leave_id = leave.id
                    rec.leave_type_id = leave.holiday_status_id.id
                    rec.is_on_leave = True
                    
                    # Generate short code from leave type name (Hybrid: Explicit + Dynamic)
                    leave_type_name = leave.holiday_status_id.name or ''
                    if 'sick' in leave_type_name.lower():
                        rec.leave_status_code = 'SL'
                    elif 'annual' in leave_type_name.lower():
                        rec.leave_status_code = 'AL'
                    elif 'maternity' in leave_type_name.lower():
                        rec.leave_status_code = 'MTL'
                    elif 'marriage' in leave_type_name.lower():
                        rec.leave_status_code = 'MRL'
                    elif 'paternity' in leave_type_name.lower():
                        rec.leave_status_code = 'PL'
                    elif 'compassionate' in leave_type_name.lower() or 'bereavement' in leave_type_name.lower():
                        rec.leave_status_code = 'CL'
                    elif 'lwop' in leave_type_name.lower() or 'without pay' in leave_type_name.lower():
                        rec.leave_status_code = 'LWOP'
                    else:
                        words = leave_type_name.split()
                        if len(words) > 1:
                            rec.leave_status_code = ''.join([w[0].upper() for w in words[:2]])
                        else:
                            rec.leave_status_code = leave_type_name[:2].upper() if len(leave_type_name) >= 2 else leave_type_name.upper()
                        
            except Exception as e:
                _logger.warning(f"Error computing leave status for attendance {rec.id}: {e}")
                continue    

      # ===============================================================
    #  Lunch Out Action - Bank Policy: After 12:00 PM
    # ===============================================================
    def action_lunch_out(self):
        """
        Record lunch_out time for reporting purposes only.
        Bank Policy: Lunch Out allowed from 12:00 PM onwards (until 7:00 PM)
        """
        self.ensure_one()
        employee = self.employee_id
        if not employee:
            raise UserError(_("Attendance record has no employee linked."))

        now_utc = fields.Datetime.now()
        
        # Convert to employee timezone for validation
        try:
            tz_name = employee.tz or self.env.user.tz or 'UTC'
            employee_tz = pytz.timezone(tz_name)
        except Exception:
            employee_tz = pytz.utc
        
        now_local = pytz.utc.localize(now_utc).astimezone(employee_tz)
        current_time = now_local.time()

        # Bank Policy: Lunch Out allowed from 12:00 PM onwards
        if current_time < time(12, 0):
           raise UserError(_("Lunch Out is only allowed from 12:00 PM onwards."))
        
        # Validate not too late (before 7:00 PM)
        if current_time > time(19, 0):
            raise UserError(_("Lunch Out recording is only allowed before 7:00 PM."))

        # Check directly on self
        if self.lunch_out:
            raise UserError(_("You have already recorded Lunch Out today."))
            
        if self.check_out:
             raise UserError(_("Cannot record Lunch Out on a checked-out attendance (Open attendance required)."))

        # Record lunch_out without closing attendance
        self.lunch_out = now_utc
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Lunch Out Recorded"),
                'message': _("Lunch Out time registered successfully at %s.") % now_local.strftime('%I:%M %p'),
                'sticky': False,
                'type': 'success',
            },
        }

    # ===============================================================
    #  Lunch In Action
    # ===============================================================
    def action_lunch_in(self):
        """
        Record lunch_in time after lunch_out.
        Bank Policy: Lunch recording allowed from 12:00 PM to 7:00 PM
        """
        self.ensure_one()
        employee = self.employee_id
        if not employee:
            raise UserError(_("Attendance record has no employee linked."))

        now_utc = fields.Datetime.now()
        
        # Convert to employee timezone for validation
        try:
            tz_name = employee.tz or self.env.user.tz or 'UTC'
            employee_tz = pytz.timezone(tz_name)
        except Exception:
            employee_tz = pytz.utc
        
        now_local = pytz.utc.localize(now_utc).astimezone(employee_tz)
        current_time = now_local.time()

        # Bank Policy: Lunch recording allowed from 12:00 PM to 1:10 PM
        if current_time < time(12, 0):
            raise UserError(_("Lunch In is only allowed from 12:00 PM onwards."))
        
        if current_time > time(13, 10):
            raise UserError(_("Lunch In recording is only allowed before 1:10 PM."))

        if not self.lunch_out:
            raise UserError(_("Lunch Out must be recorded before Lunch In."))

        if now_utc <= self.lunch_out:
            raise UserError(_("Lunch In time must be after Lunch Out time."))
            
        if self.lunch_in:
             raise UserError(_("Lunch In already recorded."))

        # Record lunch_in
        self.lunch_in = now_utc
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Lunch In Recorded"),
                'message': _("Lunch In time registered successfully at %s.") % now_local.strftime('%I:%M %p'),
                'sticky': False,
                'type': 'success',
            },
        }   


        
    @api.depends('check_in', 'check_out', 'lunch_out', 'lunch_in', 'employee_id.attendance_policy_id')
    def _get_expected_schedule(self, employee, target_date, tz, employee_shifts=None):
        """
        Determine expected check-in/out times based on:
        1. Assigned Shift (Priority)
        2. Attendance Policy
        3. Employee's Calendar
        4. Hardcoded Fallback (Sat: 8-12, Mon-Fri: 8-5)
        """
        start_dt = None
        end_dt = None
        calendar = False
        
        # 1. Check Shift Schedule (Assigned)
        shift = None
        if employee_shifts is not None:
            # fast memory lookup
            target_dt_start = datetime.combine(target_date, time(0, 0))
            target_dt_end = datetime.combine(target_date, time(23, 59))
            for s in employee_shifts:
                # Basic overlap check
                if s.state == 'assigned' and s.date_start <= target_dt_end and s.date_end >= target_dt_start:
                    shift = s
                    break
        else:
            shift = self.env['ab.hr.shift.schedule'].search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'assigned'),
                ('date_start', '<=', datetime.combine(target_date, time(23, 59))),
                ('date_end', '>=', datetime.combine(target_date, time(0, 0)))
            ], limit=1)
        
        if shift and shift.shift_type_id.resource_calendar_id:
             calendar = shift.shift_type_id.resource_calendar_id
        
        # 2. Check Policy / Employee Calendar
        if not calendar:
            if employee.attendance_policy_id and employee.attendance_policy_id.resource_calendar_id:
                calendar = employee.attendance_policy_id.resource_calendar_id
            elif employee.resource_calendar_id:
                calendar = employee.resource_calendar_id

        # Get intervals from calendar
        if calendar:
            # We need to find the interval for this specific day
            day_start = tz.localize(datetime.combine(target_date, time(0, 0)))
            day_end = tz.localize(datetime.combine(target_date, time(23, 59, 59)))
            
            # work_intervals_batch returns start, end, record
            intervals = calendar._work_intervals_batch(day_start, day_end, resources=employee.resource_id, tz=tz)
            employee_intervals = list(intervals.get(employee.resource_id.id, []))
            
            if employee_intervals:
                # Assuming continuous shift or taking first check-in and last check-out
                start_dt = employee_intervals[0][0] # First interval start
                end_dt = employee_intervals[-1][1]  # Last interval end
        
        # 3. Fallback if no calendar or no intervals found for today
        if not start_dt or not end_dt:
            # Logic for Saturday: 8-12
            if target_date.weekday() == 5: # Saturday
                 start_time = time(8, 0)
                 end_time = time(12, 0)
            elif target_date.weekday() == 6: # Sunday
                 return None, None, calendar # Holiday usually
            else: # Mon-Fri
                 start_time = time(8, 0)
                 end_time = time(17, 0)
            
            start_dt = tz.localize(datetime.combine(target_date, start_time))
            end_dt = tz.localize(datetime.combine(target_date, end_time))
            
        return start_dt, end_dt, calendar

    @api.depends('check_in', 'check_out', 'lunch_out', 'lunch_in', 'employee_id.attendance_policy_id', 'employee_id.resource_calendar_id')
    def _compute_attendance_analysis(self, employee_tz=False):
        """
        Computed based on Shift / Calendar / Policy.
        Supports dynamic shifts and Saturday logic.
        """
        # --- PREFETCH SHIFTS OPTIMIZATION ---
        # Build cache of shifts for relevant employees and dates to avoid N+1 queries
        try:
            records_with_checkin = self.filtered(lambda r: r.employee_id and r.check_in)
            if len(records_with_checkin) > 1: # Only prefetch if multiple records
                employee_ids = records_with_checkin.mapped('employee_id').ids
                check_ins = records_with_checkin.mapped('check_in')
                if check_ins:
                    min_date = min(check_ins).replace(hour=0, minute=0, second=0)
                    max_date = max(check_ins).replace(hour=23, minute=59, second=59)
                    
                    # Fetch all potentially relevant shifts
                    shifts = self.env['ab.hr.shift.schedule'].search([
                        ('employee_id', 'in', employee_ids),
                        ('state', '=', 'assigned'),
                        ('date_start', '<=', max_date),
                        ('date_end', '>=', min_date)
                    ])
                    
                    # Group by employee for fast lookup
                    shift_cache = {} # {employee_id: [shift1, shift2]}
                    for s in shifts:
                        if s.employee_id.id not in shift_cache:
                            shift_cache[s.employee_id.id] = []
                        shift_cache[s.employee_id.id].append(s)
                else:
                    shift_cache = {}
            else:
                shift_cache = {} # Single record or none, let standard search handle it
        except Exception as e:
            _logger.warning(f"Shift prefetch failed: {e}")
            shift_cache = {}

        for att in self:
            att.is_late = False
            att.late_minutes = 0.0
            att.late_display = ''
            att.late_duration_display = ''
            att.early_out_minutes = 0.0
            # att.early_display = ''  # Removed undefined field
            att.early_out_duration_display = ''
            att.attendance_status = 'on_time'
            
            if not att.employee_id or not att.check_in:
                continue

            # Use employee tz safely
            try:
                tz_name = att.employee_id.tz or self.env.user.tz or 'UTC'
                employee_tz = pytz.timezone(tz_name)
            except Exception:
                employee_tz = pytz.utc
            
            # Convert UTC datetimes to local for comparison
            try:
                check_in_local = pytz.utc.localize(att.check_in).astimezone(employee_tz)
            except Exception:
                check_in_local = att.check_in
                
            target_date = check_in_local.date()
            
            # --- GET EXPECTED SCHEDULE ---
            # Pass cached shifts for this employee if available
            att_shifts = shift_cache.get(att.employee_id.id)
            expected_start, expected_end, calendar = self._get_expected_schedule(
                att.employee_id, target_date, employee_tz, employee_shifts=att_shifts
            )
            
            if not expected_start:
                # No schedule for today (Rest Day) - Mark as Overtime or ignore?
                # For now, we just skip "Late" analysis, effectively treating it as on_time (or purely extra)
                continue

            # --- 1. LATE IN CALCULATION ---
            # Get tolerance from calendar or default 15 mins
            tolerance_minutes = 15.0
            if calendar and hasattr(calendar, 'tolerance_late_check_in'):
                tolerance_minutes = calendar.tolerance_late_check_in
            
            late_threshold_time = expected_start + timedelta(minutes=tolerance_minutes)

            is_late_check_in = False
            if check_in_local > late_threshold_time:
                is_late_check_in = True
                att.is_late = True
                
                # Calculate lateness from STANDARD start time (not threshold)
                lateness_delta = check_in_local - expected_start
                att.late_minutes = round(lateness_delta.total_seconds() / 60.0, 2)
                
                # Format is_late
                att.late_duration_display = self._format_duration(att.late_minutes)
                att.late_display = att.late_duration_display # Populate both
                att.attendance_status = 'late_in'


            # ========================================================
            # 2. EARLY OUT / MISS OUT CALCULATION
            # ========================================================
            is_early_out_check = False
            is_miss_out = False
            
            # Ensure expected_end is set before using it
            # if expected_end:
            #      if att.check_out:
            #         try:
            #             check_out_local = pytz.utc.localize(att.check_out).astimezone(employee_tz)
            #         except Exception:
            #             check_out_local = att.check_out

            #         # Grace period for early out (e.g. 5 mins)
            #         # If checkout is earlier than expected_end - 5 mins
            #         early_out_threshold = expected_end - timedelta(minutes=5)
                    
            #         if check_out_local < early_out_threshold:
            #             is_early_out_check = True
            #             # Calculate how early from standard end time
            #             earliness_delta = expected_end - check_out_local
            #             att.early_out_minutes = round(earliness_delta.total_seconds() / 60.0, 2)
            #             att.early_out_duration_display = self._format_duration(att.early_out_minutes)
            #             # att.early_display = att.early_out_duration_display # Removed undefined field
            #      else:
            #         # No check_out -> determine if it's a miss_out
            #         try:
            #             today_local = pytz.utc.localize(datetime.utcnow()).astimezone(employee_tz).date()
            #         except Exception:
            #             today_local = date.today()

            #         checkin_local_date = check_in_local.date()
                    
            #         # Miss out if it's a previous day's attendance
            #         if checkin_local_date < today_local:
            #             is_miss_out = True
            #         # OR if same day but past miss-out deadline (e.g. 2 hours after shift end)
            #         elif checkin_local_date == today_local:
            #             now_local = pytz.utc.localize(datetime.utcnow()).astimezone(employee_tz)
                        
            #             # Safe logic: Shift End + 3 hours
            #             miss_out_deadline = expected_end + timedelta(hours=3)
                        
            #             # But for Ahadu (8-5), deadline is 19:00 (which is +2 hours from 17:00)
            #             if expected_end.hour == 17:
            #                  miss_out_deadline = expected_start.replace(hour=19, minute=0)
            #             if expected_end.hour == 12: # Saturday
            #                  miss_out_deadline = expected_start.replace(hour=14, minute=0)

            #             if now_local >= miss_out_deadline:
            #                 is_miss_out = True

            # # ========================================================
            # # 3. COMBINED STATUS LOGIC
            # # ========================================================
            
            # if is_late_check_in and is_early_out_check:
            #     att.attendance_status = 'late_in_early_out'
            # elif is_late_check_in and is_miss_out:
            #     att.attendance_status = 'late_in_miss_out'
            # elif is_early_out_check and not is_late_check_in:
            #     att.attendance_status = 'early_out'
            # elif is_miss_out and not is_late_check_in:
            #     att.attendance_status = 'on_time_miss_out'
            # elif is_miss_out and is_late_check_in:
            #     att.attendance_status = 'late_in_miss_out'
            # elif is_late_check_in:
            #     att.attendance_status = 'late_in'
            # # else it remains 'on_time' (default)

            # # Ensure display fields are populated if they weren't already
            # if att.late_minutes > 0 and not att.late_duration_display:
            #     att.late_duration_display = att._format_duration(att.late_minutes)
            #     att.late_display = att.late_duration_display
            # if att.early_out_minutes > 0 and not att.early_out_duration_display:
            #      att.early_out_duration_display = att._format_duration(att.early_out_minutes)
            #      # att.early_display = att.early_out_duration_display
           
            if expected_end:
                 if att.check_out:
                    # FIX: If CheckIn == CheckOut (Auto-closed by system), it is MISS OUT.
                    # Or if the flag is set.
                    if att.check_in == att.check_out or att.miss_out_status_handled:
                        is_miss_out = True
                        is_early_out_check = False # Miss-out takes priority over Early-out
                    else:
                        # Normal Check Out Logic
                        try:
                            check_out_local = pytz.utc.localize(att.check_out).astimezone(employee_tz)
                        except: check_out_local = att.check_out

                        early_out_threshold = expected_end - timedelta(minutes=5)
                        
                        if check_out_local < early_out_threshold:
                            is_early_out_check = True
                            att.is_early = True
                            earliness_delta = expected_end - check_out_local
                            att.early_out_minutes = round(earliness_delta.total_seconds() / 60.0, 2)
                            att.early_out_duration_display = self._format_duration(att.early_out_minutes)
                 else:
                    # No check_out yet
                    try:
                        today_local = datetime.now(employee_tz).date()
                    except: today_local = date.today()

                    checkin_local_date = check_in_local.date()
                    
                    if checkin_local_date < today_local:
                        is_miss_out = True
                    elif checkin_local_date == today_local:
                        # Consider missed out if 3 hours past shift end
                        miss_out_deadline = expected_end + timedelta(hours=3)
                        now_local = datetime.now(employee_tz)
                        if now_local >= miss_out_deadline:
                            is_miss_out = True

            # --- 3. COMBINED STATUS LOGIC ---
            # Prioritize Miss-Out combinations over Early-Out combinations
            if is_late_check_in and is_miss_out:
                att.attendance_status = 'late_in_miss_out'
            elif is_miss_out:
                att.attendance_status = 'miss_out' # Use simple miss_out key
            elif is_late_check_in and is_early_out_check:
                att.attendance_status = 'late_in_early_out'
            elif is_early_out_check:
                att.attendance_status = 'early_out'
            elif is_late_check_in:
                att.attendance_status = 'late_in'
            else:
                att.attendance_status = 'on_time'

            # Populate empty display fields
            if att.late_minutes > 0 and not att.late_duration_display:
                att.late_duration_display = self._format_duration(att.late_minutes)
                att.late_display = att.late_duration_display
            if att.early_out_minutes > 0 and not att.early_out_duration_display:
                 att.early_out_duration_display = self._format_duration(att.early_out_minutes)


    def _format_duration(self, minutes):
        """
        Formats duration (in minutes) to:
        - "X min" if < 60
        - "Y.YY hr" (decimal) if >= 60
        """
        if minutes < 60:
            return f"{int(round(minutes))} min"
        else:
            # decimal hours
            return f"{minutes/60:.2f} hr"

    # ===================================================================
    #  OVERRIDE: worked_hours computation to subtract 1-hour lunch
    #  Bank requirement: Always subtract 1 hour lunch from total time
    #  Formula: worked_hours = (check_out - check_in) - 1 hour
    #  This ensures payroll gets net 8 hours (9 hours presence - 1 hour lunch)
    #  IMPORTANT: For miss_out cases, do NOT count time after 7:00 PM
    # ===================================================================
    # @api.depends('check_in', 'check_out', 'attendance_status')
    # def _compute_worked_hours(self):
    #     """
    #     Override Odoo's default worked_hours calculation.
    #     Bank Policy:
    #     - Always subtract 1 hour for lunch break
    #     - Total presence: 6:00 AM - 5:00 PM = 9 hours
    #     - Lunch deduction: 1 hour (automatic)
    #     - Net worked hours: 8 hours (passed to payroll)
    #     - Miss-Out: Do NOT count worked time after 7:00 PM (19:00)
    #     """
    #     for attendance in self:
    #         if attendance.check_in:
    #             try:
    #                 # Get employee timezone
    #                 tz_name = attendance.employee_id.tz or self.env.user.tz or 'UTC'
    #                 employee_tz = pytz.timezone(tz_name)
    #             except Exception:
    #                 employee_tz = pytz.utc
                
    #             # Convert check_in to local time
    #             try:
    #                 check_in_local = pytz.utc.localize(attendance.check_in).astimezone(employee_tz)
    #             except Exception:
    #                 check_in_local = attendance.check_in
                
    #             # Determine effective check_out time
    #             if attendance.check_out:
    #                 effective_check_out = attendance.check_out
    #             elif attendance.attendance_status in ['miss_out', 'late_in_miss_out', 'on_time_miss_out']:
    #                 # For miss_out: Cap worked hours at 7:00 PM (19:00)
    #                 # Do NOT count any time after 7:00 PM
    #                 missout_deadline = employee_tz.localize(
    #                     datetime.combine(check_in_local.date(), time(19, 0))
    #                 )
    #                 effective_check_out = missout_deadline.astimezone(pytz.utc).replace(tzinfo=None)
    #             else:
    #                 # No check_out and not miss_out yet -> 0 hours
    #                 attendance.worked_hours = 0.0
    #                 continue
                
    #             # Calculate total presence time
    #             worked_timedelta = effective_check_out - attendance.check_in
    #             total_hours = worked_timedelta.total_seconds() / 3600.0
                
    #             # Bank Policy: Subtract 1 hour for lunch ONLY if it's a full working day (> 5 hours)
    #             # For Saturdays (8-12), no lunch deduction should be applied.
                
    #             # We can deduce based on total_hours or expected schedule
    #             # If total_hours is small (e.g. < 5), assuming half-day or short shift => No lunch deduction
                
    #             deduction = 0.0
    #             if total_hours >= 5.0:
    #                 deduction = 1.0
                
    #             net_worked_hours = max(0, total_hours - deduction)
                
    #             attendance.worked_hours = round(net_worked_hours, 2)
    #         else:
    #             attendance.worked_hours = 0.0

    @api.depends('check_in', 'check_out', 'attendance_status')
    def _compute_worked_hours(self):
        """
        Override worked_hours.
        If Miss-Out (CheckIn == CheckOut), worked_hours = 0.
        """
        for attendance in self:
            if attendance.check_in and attendance.check_out:
                # CRITICAL: If Miss-Out (Auto-closed), worked hours must be 0
                if attendance.check_in == attendance.check_out or attendance.miss_out_status_handled:
                    attendance.worked_hours = 0.0
                    continue
                
                worked_timedelta = attendance.check_out - attendance.check_in
                total_hours = worked_timedelta.total_seconds() / 3600.0
                
                # Bank Policy: Subtract 1 hour for lunch if worked > 5 hours
                deduction = 0.0
                if total_hours >= 5.0:
                    deduction = 1.0
                
                net_worked_hours = max(0, total_hours - deduction)
                attendance.worked_hours = round(net_worked_hours, 2)
            else:
                attendance.worked_hours = 0.0
        
    # ===================================================================
    #  3. OVERTIME/UNDER TIME HELPER & ORM OVERRIDES
    # ===================================================================

    def _recompute_overtime_and_undertime(self):
        for att in self.browse(self.ids):
            vals_to_write = {'extra_hours': 0.0, 'under_time_hours': 0.0}
            if att.check_out and att.employee_id and att.employee_id.resource_calendar_id:
                tz = self._get_employee_tz()  # safe method
                try:
                    check_in_local = pytz.utc.localize(att.check_in).astimezone(tz)
                except Exception:
                    check_in_local = att.check_in

                day_start_local = check_in_local.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end_local = day_start_local + timedelta(days=1)

                intervals_dict = att.employee_id.resource_calendar_id._work_intervals_batch(
                    day_start_local, day_end_local, resources=att.employee_id.resource_id, tz=tz
                )
                work_intervals = list(intervals_dict.get(att.employee_id.resource_id.id, []))

                scheduled_hours = sum((interval[1] - interval[0]).total_seconds() / 3600 for interval in work_intervals)

                if scheduled_hours > 0 and att.worked_hours > 0:
                    difference = att.worked_hours - scheduled_hours
                    if difference > 0.01:
                        vals_to_write['extra_hours'] = round(difference, 2)
                    elif difference < -0.01:
                        vals_to_write['under_time_hours'] = round(difference, 2)

            if att.extra_hours != vals_to_write['extra_hours'] or att.under_time_hours != vals_to_write['under_time_hours']:
                att.sudo()._write(vals_to_write)
    
    @api.model_create_multi
    def create(self, vals_list):
        new_records = self.browse()  # ✅ initialize empty recordset
        for vals in vals_list:
            if 'employee_id' in vals and 'check_in' in vals:
                employee = self.env['hr.employee'].browse(vals['employee_id'])
                 #  FIXED: derive timezone from employee record safely
                try:
                    employee_tz = pytz.timezone(employee.tz or self.env.user.tz or 'UTC')
                except Exception:
                    employee_tz = pytz.utc

                check_in_dt = fields.Datetime.to_datetime(vals.get('check_in'))
                # employee_tz = pytz.timezone(self.env.user.tz or 'UTC')
                # employee_tz = self._get_employee_tz()
                # employee_tz = self.env['hr.attendance'].browse()._get_employee_tz() # dummy browse for tz method

                check_in_local = pytz.utc.localize(check_in_dt).astimezone(employee_tz)


                # --- 1. Enforce minimum punch-in time (6:00 AM) ---
                if check_in_local.time() < time(6, 0):
                    raise ValidationError(_("Check-in not allowed before 06:00 AM."))

                # --- 1.5. Check for Approved Leave ---
                # Bank Policy: Block check-in if user is on approved leave
                # Unless it's a "Work From Home" or similar type if applicable, but general rule is Block.
                on_leave = self.env['hr.leave'].search([
                    ('employee_id', '=', employee.id),
                    ('state', '=', 'validate'),
                    ('request_date_from', '<=', check_in_local.date()),
                    ('request_date_to', '>=', check_in_local.date()),
                ], limit=1)
                
                if on_leave:
                    # Optional: Allow check-in if leave is less than full day? 
                    # For now, strict blocking as per requirement.
                    raise ValidationError(_("You cannot check in today because you are on approved leave: %s") % on_leave.holiday_status_id.name)

                 # --- 2️⃣ Detect lunch punches (12:00–13:30) ---
                is_lunch_punch = (
                    ('lunch_in' in vals or 'lunch_out' in vals)
                    or (time(12, 0) <= check_in_local.time() <= time(13, 30))
                )
                # --- 2. Handle open attendances (Miss-Out scenario) ---
                # Search for any open attendance for this employee, regardless of date, not handled as miss_out
                open_att = self.search([
                    ('employee_id', '=', employee.id),
                    ('check_out', '=', False),
                    ('miss_out_status_handled', '=', False) # Only consider if not already processed
                ], limit=1, order='check_in desc') # Get the most recent open one

                if open_att:
                    # Convert open attendance check_in to employee timezone
                    if open_att.check_in:
                        open_att_check_in_local = pytz.utc.localize(open_att.check_in).astimezone(employee_tz)
                    else:
                        open_att_check_in_local = check_in_local  # fallback

                    open_att_date = open_att_check_in_local.date()
                    new_att_date = check_in_local.date()

                    if new_att_date == open_att_date:
                        # SAME DAY open attendance exists
                        if is_lunch_punch:
                        #  Allow lunch punch – skip validation
                           _logger.info(f"Lunch punch recorded for {employee.name} on {new_att_date}")
                        else:
                            #  Block duplicate normal punches
                            raise ValidationError(
                                _("Open attendance already exists for today (%s). Please check out first.")
                                % open_att_date.strftime('%Y-%m-%d')
                            )
                        
                    elif new_att_date > open_att_date:
                        # PAST DAY open attendance → mark as Miss-Out
                        # Bank Policy: Leave check_out EMPTY for miss-out cases
                        
                        # Determine status based on whether they were late or on-time
                        if open_att.is_late:
                            miss_out_status = 'late_in_miss_out'
                        else:
                            miss_out_status = 'on_time_miss_out'
                        
                        # Write safely to Odoo - DO NOT fill check_out field
                        open_att.sudo().write({
                            # 'check_out': LEAVE EMPTY per bank policy
                            'attendance_status': miss_out_status,
                            'miss_out_status_handled': True,
                            # 'check_out_method': NOT SET since no checkout recorded
                        })

                        # Log message for employee
                        open_att.message_post(body=_(
                            "Automatically marked as Miss-Out (prior to new check-in on %s). "
                            "Previous day %s had no checkout by 7:00 PM deadline. "
                            "Check-out field left empty per bank policy."
                        ) % (new_att_date.strftime('%Y-%m-%d'), open_att_date.strftime('%Y-%m-%d')))
                        _logger.info(f"Attendance {open_att.id} for {employee.name} marked as {miss_out_status} (check_out left empty).")
 
                    #  Continue creating new attendance (normal or lunch)
               
                # --- 3. Leave and Duty Request checks (unchanged) ---
                domain_leave = [
                    ('employee_id', '=', employee.id),
                    ('state', '=', 'validate'),
                    ('date_from', '<=', check_in_dt),
                    ('date_to', '>=', check_in_dt),
                ]
                if self.env['hr.leave'].search_count(domain_leave):
                    raise ValidationError(_("Check-in failed for %s. The employee is on an approved leave.") % employee.name)

                domain_duty = [
                    ('employee_id', '=', employee.id),
                    ('state', '=', 'approved'),
                    ('date_from', '<=', check_in_dt),
                    ('date_to', '>=', check_in_dt),
                ]
                if self.env['ab.hr.duty.request'].search_count(domain_duty) > 0:
                    raise ValidationError(_("Check-in failed for %s. The employee is on an approved duty request.") % employee.name)
    
        # records = super().create(vals)
         # Call super to actually create records
        record = super(HrAttendance, self).create(vals)

         # --- Skip work time logic for lunch punches ---
        if is_lunch_punch:
            _logger.info(f"Skipping working time calculation for lunch punch: {employee.name}")
        else:
            # Skip analysis during batch import to prevent N+1 query problem
            if not self.env.context.get('skip_analysis_on_import'):
                record._compute_attendance_analysis(employee_tz)
            else:
                _logger.debug(f"Skipping analysis for batch import: {employee.name}")

        new_records |= record

        return new_records
        
    
    def write(self, vals):
        res = super(HrAttendance, self).write(vals)

        if any(k in vals for k in ('check_in', 'check_out', 'lunch_in', 'lunch_out')):
            self._compute_attendance_analysis()
            self._compute_late_minutes()
            self._compute_early_minutes()
            self._compute_is_late()
            self._compute_is_early()
            try:
                for rec in self:
                    rec._recompute_overtime_and_undertime()
            except Exception as e:
                _logger.exception("Failed to recompute overtime in write: %s", e)
        return res

    

    # ===================================================================
    #  4. BUSINESS LOGIC & CRON JOBS
    # ===================================================================

    @api.model
    def _process_punch(self, employee_id, punch_type, punch_dt=None, method='Manual', gps_coords=None):
        """
        Main method to handle all types of punches (check-in, check-out, lunch-out, lunch-in).
        :param employee_id: ID of the employee.
        :param punch_type: 'check_in', 'check_out', 'lunch_out', 'lunch_in'.
        :param punch_dt: The datetime of the punch (defaults to now_utc if None).
        :param method: The method of punch (e.g., 'Biometric', 'PC', 'Mobile', 'Manual').
        :param gps_coords: GPS coordinates if available.
        """
        # self.ensure_one() # This method is typically called on a specific attendance record if modifying,
                          # but here it's an API model method so we will use self.env.
        employee = self.env['hr.employee'].browse(employee_id)
        if not employee:
            raise UserError(_("Employee not found."))

        now_utc = punch_dt or fields.Datetime.now()
        # employee_tz = self.env['hr.attendance'].browse()._get_employee_tz() # dummy browse for tz method
        # now_local = pytz.utc.localize(now_utc).astimezone(employee_tz)
        try:
            employee_tz = pytz.timezone(employee.tz or self.env.user.tz or 'UTC')
        except Exception:
            employee_tz = pytz.utc

        now_local = pytz.utc.localize(now_utc).astimezone(employee_tz)

        
        # Search for the open attendance record for today (if any)
        # Or an open record from previous day not yet handled as miss-out
        open_attendance = self.search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False),
            ('miss_out_status_handled', '=', False),
            ('check_in', '<=', now_utc.replace(hour=23, minute=59, second=59)) # Check for records up to end of today
        ], limit=1, order='check_in desc') # Get the most recent open one

        if punch_type == 'check_in':
            # 1. Validate Check-in time
            if now_local.time() < time(6, 0):
                raise ValidationError(_("Check-in not allowed before 06:00 AM."))
            
            if open_attendance:
                open_check_date = pytz.utc.localize(open_attendance.check_in).astimezone(employee_tz).date()
                if open_check_date == now_local.date():
                    raise ValidationError(_("You are already checked in for today."))
                else:
                    _logger.info("Employee %s has an open attendance from previous day %s", employee.name, open_check_date)

            # Create new attendance record
            new_attendance_vals = {
                'employee_id': employee.id,
                'check_in': now_utc,
                'check_in_method': method,
                'check_in_gps': gps_coords,
                'punch_type': 'check_in',
            }
            return self.create(new_attendance_vals)

        if punch_type == 'check_out':
            if not open_attendance:
                raise ValidationError(_("You are not checked in to check out."))

            # Ensure it's for the same day as check_in (or within reasonable bounds)
            open_att_check_in_local = pytz.utc.localize(open_attendance.check_in).astimezone(employee_tz)
            if open_att_check_in_local.date() != now_local.date():
                raise ValidationError(_("Cannot check out for a previous day's attendance. Please contact HR for manual adjustment."))

            # 2. Validate Check-out time & Miss-Out (midnight boundary)
            if now_local.time() > time(23, 59): # After midnight
                open_attendance.write({
                    'attendance_status': 'miss_out',
                    'miss_out_status_handled': True,
                    'check_out_method': method, # Use the method that triggered this, e.g., 'Manual' if UI button, 'System' if cron
                    # Do NOT fill check_out. Leave it blank as per requirement "leave the check out blank no fill date time"
                })
                open_attendance.message_post(body=_("Employee attempted to check out after midnight. Marked as Miss-Out."))
                raise ValidationError(_("Check-out not allowed after midnight. Your attendance has been marked as Miss-Out."))
            
            # If punch is before 16:55, it will be marked as Early-Out by `_compute_attendance_analysis`
            open_attendance.write({
                'check_out': now_utc,
                'check_out_method': method,
                'check_out_gps': gps_coords,
                'punch_type': 'check_out',
            })
            return open_attendance

        if punch_type == 'lunch_out':
            # Bank Policy: Lunch Out allowed from 12:00 PM onwards
            if not open_attendance:
                raise ValidationError(_("You must be checked in to go for lunch."))

            # Ensure it's for the same day as check_in
            open_att_check_in_local = pytz.utc.localize(open_attendance.check_in).astimezone(employee_tz)
            if open_att_check_in_local.date() != now_local.date():
                raise ValidationError(_("Cannot punch lunch for a previous day's attendance."))

            # Validate Lunch Out time: Must be after 12:00 PM
            if now_local.time() < time(12, 0):
                raise ValidationError(_("Lunch Out is only allowed from 12:00 PM onwards."))
            
            if open_attendance.lunch_out:
                raise ValidationError(_("You are already on lunch or have already taken lunch out today."))

            open_attendance.write({
                'lunch_out': now_utc,
                'punch_type': 'lunch_out',
            })
            _logger.info(f"Lunch Out recorded for {employee.name} at {now_local.strftime('%H:%M:%S')}")
            return open_attendance

        elif punch_type == 'lunch_in':
            if not open_attendance or not open_attendance.lunch_out:
                raise ValidationError(_("You must be on lunch to punch back in from lunch."))

            # Ensure it's for the same day as check_in
            open_att_check_in_local = pytz.utc.localize(open_attendance.check_in).astimezone(employee_tz)
            if open_att_check_in_local.date() != now_local.date():
                raise ValidationError(_("Cannot punch lunch for a previous day's attendance."))

            # Validate Lunch In time: Must be before 7:00 PM (19:00)
            # Bank Policy: Lunch punches are for reporting only, allowed until 7:00 PM
            if now_local.time() > time(19, 0):
                raise ValidationError(_("Lunch In recording is only allowed before 7:00 PM."))
            
            # Validate Lunch In is after Lunch Out
            lunch_out_local = pytz.utc.localize(open_attendance.lunch_out).astimezone(employee_tz)
            if now_local <= lunch_out_local:
                raise ValidationError(_("Lunch In time must be after Lunch Out time."))
                
            open_attendance.write({
                'lunch_in': now_utc,
                'punch_type': 'lunch_in',
            })
            _logger.info(f"Lunch In recorded for {employee.name} at {now_local.strftime('%H:%M:%S')}")
            return open_attendance
        else:
            raise ValidationError(_("Invalid punch type provided."))

    @api.model
    def _cron_check_missed_outs(self):
        """
        Bank Policy: Cron job to mark 'Miss-Out' for attendances with no checkout by 7:00 PM.
        
        - Runs daily (ideally after 7:00 PM or at midnight)
        - Marks previous day's unclosed attendances as Miss-Out
        - Leaves check_out field EMPTY (bank policy requirement)
        - Allows next day check-in to proceed normally
        """
        _logger.info("Running cron job: _cron_check_missed_outs (Bank Policy)")
        
        now_utc = fields.Datetime.now()
        # Check attendances from yesterday and earlier that are still open
        yesterday_utc_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)

        # Find open attendances that haven't been marked as miss_out yet
        attendances_to_check = self.search([
            ('check_in', '<', yesterday_utc_start),  # Before today
            ('check_out', '=', False),  # No checkout
            ('miss_out_status_handled', '=', False),  # Not yet processed
        ])
        
        for att in attendances_to_check:
            try:
                employee_tz = att._get_employee_tz()
                check_in_local = pytz.utc.localize(att.check_in).astimezone(employee_tz)
                
                # Bank Policy: Leave check_out EMPTY for miss-out
                # Determine status based on whether they were late or on-time
                if att.is_late:
                    status = 'late_in_miss_out'
                else:
                    status = 'on_time_miss_out'
                
                att.sudo().write({
                    # DO NOT set check_out - leave it empty per bank policy
                    'attendance_status': status,
                    'miss_out_status_handled': True,
                    # check_out_method not set since there's no checkout
                })
                
                att.message_post(body=_(
                    "Automatically marked as Miss-Out by system cron (no checkout recorded by 7:00 PM deadline). "
                    "Check-out field left empty per bank policy."
                ))
                _logger.info(f"Cron: Marked attendance {att.id} for {att.employee_id.name} as {status} (check_out left empty).")
            except Exception as e:
                _logger.error(f"Error processing miss-out for attendance {att.id}: {e}")

    # ===================================================================
    #  5. HELPER METHODS FOR LEAVE INTEGRATION
    # ===================================================================
    @api.model
    def _get_employee_leave_status(self, employee_id, target_date):
        """
        Helper method to get leave status for an employee on a specific date.
        Returns dict with leave information or False if not on leave.
        """
        if isinstance(target_date, datetime):
            target_date = target_date.date()
        
        leaves = self.env['hr.leave'].search([
            ('employee_id', '=', employee_id),
            ('state', '=', 'validate'),
            ('request_date_from', '<=', target_date),
            ('request_date_to', '>=', target_date),
        ], limit=1)
        
        if leaves:
            leave = leaves[0]
            leave_type_name = leave.holiday_status_id.name or ''
            
            # Generate short code (Hybrid: Explicit + Dynamic)
            leave_type_name = leave.holiday_status_id.name or ''
            if 'sick' in leave_type_name.lower():
                code = 'SL'
            elif 'annual' in leave_type_name.lower():
                code = 'AL'
            elif 'maternity' in leave_type_name.lower():
                code = 'MTL'
            elif 'marriage' in leave_type_name.lower():
                code = 'MRL'
            elif 'paternity' in leave_type_name.lower():
                code = 'PL'
            elif 'compassionate' in leave_type_name.lower() or 'bereavement' in leave_type_name.lower():
                code = 'CL'
            elif 'lwop' in leave_type_name.lower() or 'without pay' in leave_type_name.lower():
                code = 'LWOP'
            else:
                words = leave_type_name.split()
                if len(words) > 1:
                    code = ''.join([w[0].upper() for w in words[:2]])
                else:
                    code = leave_type_name[:2].upper() if len(leave_type_name) >= 2 else leave_type_name.upper()
            
            return {
                'leave_id': leave.id,
                'leave_type_id': leave.holiday_status_id.id,
                'leave_type_name': leave_type_name,
                'leave_status_code': code,
                'is_on_leave': True
            }
        
        return False
    
    # ===================================================================
    #  6. DASHBOARD METHOD
    # ===================================================================
    @api.model
    @api.model
    def get_attendance_dashboard_data(self, filters=None):
        if filters is None:
            filters = {}
            
        utc_tz = pytz.utc
        today_utc_start = fields.Datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).astimezone(utc_tz)
        today_utc_end = today_utc_start + timedelta(days=1)
        
        all_employees = self.env['hr.employee'].search([('active', '=', True)])
        
        attendances_today = self.search([('check_in', '>=', today_utc_start), ('check_in', '<', today_utc_end)])
        present_employee_ids = attendances_today.mapped('employee_id').ids
        
        leaves_today = self.env['hr.leave'].search([('state', '=', 'validate'), ('date_from', '<', today_utc_end), ('date_to', '>', today_utc_start)])
        on_leave_ids = leaves_today.mapped('employee_id').ids
        
        absent_employee_ids = [e.id for e in all_employees if e.id not in present_employee_ids and e.id not in on_leave_ids]
        late_attendances = attendances_today.filtered(lambda a: a.is_late)
        early_out_attendances = attendances_today.filtered(lambda a: a.early_out_minutes > 0)
        miss_out_attendances = attendances_today.filtered(lambda a: a.attendance_status in ['miss_out', 'late_in_miss_out', 'on_time_miss_out'])
        
        # Lunch participation
        lunch_recorded = attendances_today.filtered(lambda a: a.lunch_out)
        lunch_participation_rate = (len(lunch_recorded) / len(attendances_today) * 100) if attendances_today else 0
        
        # Overtime (if model exists)
        overtime_hours_today = 0
        if 'ab.hr.overtime' in self.env:
            overtime_records = self.env['ab.hr.overtime'].search([('date', '=', fields.Date.today())])
            overtime_hours_today = sum(overtime_records.mapped('duration'))

        kpi_data = {
            'present_today': len(present_employee_ids),
            'absent_today': len(absent_employee_ids),
            'on_leave_today': len(on_leave_ids),
            'late_today': len(late_attendances),
            'early_out_today': len(early_out_attendances),
            'miss_out_today': len(miss_out_attendances),
            'lunch_recorded_today': len(lunch_recorded),
            'lunch_participation_rate': round(lunch_participation_rate, 1),
            'overtime_hours_today': round(overtime_hours_today, 2),
            'domain_present': [('id', 'in', attendances_today.ids)],
            'domain_absent': [('id', 'in', absent_employee_ids)],
            'domain_late': [('id', 'in', late_attendances.ids)],
            'domain_early_out': [('id', 'in', early_out_attendances.ids)],
            'domain_miss_out': [('id', 'in', miss_out_attendances.ids)],
            'domain_on_leave': [('id', 'in', leaves_today.ids)],
        }
        
        chart_data = {}
        
        employees_by_calendar = fields.defaultdict(lambda: self.env['hr.employee'])
        for emp in all_employees:
            if emp.resource_calendar_id:
                employees_by_calendar[emp.resource_calendar_id] |= emp
        
        scheduled_today_count = 0
        for calendar, employees in employees_by_calendar.items():
            intervals_dict = calendar._work_intervals_batch(today_utc_start, today_utc_end, resources=employees.resource_id)
            scheduled_today_count += sum(1 for resource_id in employees.resource_id.ids if intervals_dict.get(resource_id))
        not_scheduled_today_count = len(all_employees) - scheduled_today_count
        chart_data['schedule_status'] = {'labels': ['Scheduled', 'Not Scheduled'], 'datasets': [{'data': [scheduled_today_count, not_scheduled_today_count], 'backgroundColor': ['#28a745', '#6c757d']}]}
        
        today_date = date.today()
        labels = [(today_date - timedelta(days=i)).strftime('%a, %b %d') for i in range(6, -1, -1)]
        date_range = [today_date - timedelta(days=i) for i in range(6, -1, -1)]
        late_data = [self.search_count([('is_late', '=', True), ('check_in', '>=', fields.Date.to_string(d)), ('check_in', '<', fields.Date.to_string(d + timedelta(days=1)))]) for d in date_range]
        early_out_data = [self.search_count([('early_out_minutes', '>', 0), ('check_in', '>=', fields.Date.to_string(d)), ('check_in', '<', fields.Date.to_string(d + timedelta(days=1)))]) for d in date_range]
        miss_out_data = [self.search_count([('attendance_status', 'in', ['miss_out', 'late_in_miss_out', 'on_time_miss_out']), ('check_in', '>=', fields.Date.to_string(d)), ('check_in', '<', fields.Date.to_string(d + timedelta(days=1)))]) for d in date_range]

        chart_data['attendance_exceptions'] = {
            'labels': labels,
            'datasets': [
                {'label': 'Late Arrivals', 'data': late_data, 'borderColor': '#ff6384', 'backgroundColor': '#ff638444', 'fill': True},
                {'label': 'Early Outs', 'data': early_out_data, 'borderColor': '#36a2eb', 'backgroundColor': '#36a2eb44', 'fill': True},
                {'label': 'Missed Outs', 'data': miss_out_data, 'borderColor': '#ffcd56', 'backgroundColor': '#ffcd5644', 'fill': True},
            ]
        }

        chart_data['approval_status'] = {'labels': ['Draft', 'Submitted', 'Approved', 'Rejected'], 'datasets': [{'data': [
            self.env['ab.hr.attendance.sheet'].search_count([('state', '=', 'draft')]), self.env['ab.hr.attendance.sheet'].search_count([('state', '=', 'submitted')]),
            self.env['ab.hr.attendance.sheet'].search_count([('state', '=', 'approved')]), self.env['ab.hr.attendance.sheet'].search_count([('state', '=', 'rejected')]),
        ], 'backgroundColor': ['#36a2eb', '#ffce56', '#4bc0c0', '#ff6384']}]}
        
        # Schedule Status (Today's distribution)
        on_time_today = self.search_count([('check_in', '>=', today_utc_start), ('check_in', '<', today_utc_end), ('is_late', '=', False)])
        late_today = len(present_employee_ids) - on_time_today
        
        chart_data['schedule_status'] = {'labels': ['On Time', 'Late', 'Absent'], 'datasets': [{'data': [
            on_time_today, late_today, len(absent_employee_ids)
        ], 'backgroundColor': ['#4bc0c0', '#ffce56', '#ff6384']}]}

        # Department Performance (Split into Head Office and Branches)
        # Performance Logic: (Present / (Total - On Leave)) * 100
        ho_data = []
        branch_data = []
        
        # Get all departments that have employees
        depts_with_employees = self.env['hr.department'].search([])
        
        for dept in depts_with_employees:
            dept_employees = all_employees.filtered(lambda e: e.department_id == dept)
            if not dept_employees:
                continue
                
            # Corrected Performance Logic: (Present / (Total - On Leave Today)) * 100
            # Total - On Leave = People who were actually supposed to be here (Scheduled)
            dept_present = len([e for e in dept_employees if e.id in present_employee_ids])
            dept_on_leave = len([e for e in dept_employees if e.id in leaves_today.employee_id.ids])
            
            effective_total = len(dept_employees) - dept_on_leave
            if effective_total > 0:
                dept_rate = (dept_present / effective_total * 100)
            else:
                dept_rate = 0 # No one was supposed to be here
                
            entry = {'dept': dept.name, 'rate': round(dept_rate, 1)}
            
            # Categorize: "District North" and "District South" are Branches, others are HO
            if "District" in (dept.name or ""):
                branch_data.append(entry)
            else:
                ho_data.append(entry)
        
        # Head Office Performance (Top 10)
        ho_data = sorted(ho_data, key=lambda x: x['rate'], reverse=True)[:10]
        chart_data['head_office_performance'] = {
            'labels': [d['dept'] for d in ho_data],
            'datasets': [{'label': 'Performance %', 'data': [d['rate'] for d in ho_data], 
                         'backgroundColor': '#8A0037', 'borderRadius': 5}]
        } if ho_data else False

        # Branch Performance (District Data)
        branch_data = sorted(branch_data, key=lambda x: x['rate'], reverse=True)
        chart_data['branch_performance'] = {
            'labels': [d['dept'] for d in branch_data],
            'datasets': [{'label': 'Performance %', 'data': [d['rate'] for d in branch_data], 
                         'backgroundColor': '#2E8B57', 'borderRadius': 5}] # Different color for branch
        } if branch_data else False
        
        recent_logs = self.search([('check_in', '>=', today_utc_start)], order='check_in desc', limit=10) # Increased limit for better dashboard view
        log_list = []
        status_class_map = {
            'on_time': 'text-bg-success',
            'late_in': 'text-bg-warning',
            'early_out': 'text-bg-info',
            'late_in_early_out': 'text-bg-danger',
            'miss_out': 'text-bg-secondary',
            'late_in_miss_out': 'text-bg-secondary', # Can be refined to warning/danger
            'on_time_miss_out': 'text-bg-secondary', # Can be refined
        }
        for log in recent_logs:
            # Ensure proper timezone conversion for display
            check_in_display = fields.Datetime.context_timestamp(self, log.check_in).strftime('%H:%M:%S') if log.check_in else ''
            check_out_display = fields.Datetime.context_timestamp(self, log.check_out).strftime('%H:%M:%S') if log.check_out else ''
            lunch_out_display = fields.Datetime.context_timestamp(self, log.lunch_out).strftime('%H:%M:%S') if log.lunch_out else ''
            lunch_in_display = fields.Datetime.context_timestamp(self, log.lunch_in).strftime('%H:%M:%S') if log.lunch_in else ''

            emp_read = log.employee_id.read(['id', 'name', 'employee_id'])
            emp_dict = emp_read[0] if emp_read else {'id': False, 'name': 'Unknown', 'employee_id': ''}

            log_list.append({
                'id': log.id,
                'employee': emp_dict,
                'avatar_url': f'/web/image/hr.employee/{log.employee_id.id}/avatar_128',
                'check_in': check_in_display,
                'check_out': check_out_display,
                'lunch_out': lunch_out_display,
                'lunch_in': lunch_in_display,
                'attendance_status': dict(self._fields['attendance_status'].selection).get(log.attendance_status, ''),
                'status_class': status_class_map.get(log.attendance_status, 'text-bg-secondary'),
                'late_duration_display': log.late_duration_display,
                'early_out_duration_display': log.early_out_duration_display,
            })
        
        summary_data = {}
        # Support searching for specific employee
        target_employee_id = filters.get('employee_id')
        if target_employee_id:
            current_employee = self.env['hr.employee'].browse(target_employee_id)
        else:
            current_employee = self.env.user.employee_id
            
        if current_employee:
            today = date.today()
            
            # Use filters for month and year if provided
            month = filters.get('month')
            year = filters.get('year')
            if month and year:
                try:
                    month_start = date(int(year), int(month), 1)
                except (ValueError, TypeError):
                    month_start = today.replace(day=1)
            else:
                month_start = today.replace(day=1)
                
            # Calculate next month start correctly
            next_month_start = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
            
            scheduled_days = 0
            tz = pytz.timezone(current_employee.tz or self.env.user.tz or 'UTC')
            month_start_utc = tz.localize(datetime.combine(month_start, time.min)).astimezone(pytz.utc)
            next_month_start_utc = tz.localize(datetime.combine(next_month_start, time.min)).astimezone(pytz.utc)
            
            calendar = current_employee.resource_calendar_id
            work_dates = set()
            if calendar:
                intervals_dict = calendar._work_intervals_batch(month_start_utc, next_month_start_utc, resources=current_employee.resource_id, tz=tz)
                intervals = intervals_dict.get(current_employee.resource_id.id)
                if intervals:
                    work_dates = {interval[0].date() for interval in intervals}
                    scheduled_days = len(work_dates)

            # Correct present days calculation: Distinct days with any check-in
            query_present = "SELECT COUNT(DISTINCT(check_in::date)) FROM hr_attendance WHERE employee_id = %s AND check_in >= %s AND check_in < %s"
            self.env.cr.execute(query_present, (current_employee.id, month_start, next_month_start))
            present_days = self.env.cr.fetchone()[0] or 0
            
            # Count miss-outs for the month
            query_miss_out = "SELECT COUNT(DISTINCT(check_in::date)) FROM hr_attendance WHERE employee_id = %s AND check_in >= %s AND check_in < %s AND (attendance_status LIKE '%%miss_out%%')"
            self.env.cr.execute(query_miss_out, (current_employee.id, month_start, next_month_start))
            miss_out_days = self.env.cr.fetchone()[0] or 0
            
            # Absent calculation
            absent_days = scheduled_days - present_days
            if absent_days < 0: absent_days = 0

            # Percentage
            attendance_perc = (present_days / scheduled_days * 100) if scheduled_days > 0 else 0

            # Bulk fetch attendances and leaves
            all_month_attendances = self.search([
                ('employee_id', '=', current_employee.id),
                ('check_in', '>=', month_start_utc),
                ('check_in', '<', next_month_start_utc)
            ])
            all_month_leaves = self.env['hr.leave'].search([
                ('employee_id', '=', current_employee.id),
                ('state', '=', 'validate'),
                ('request_date_from', '<', next_month_start),
                ('request_date_to', '>=', month_start)
            ])
            
            # Holidays & Sundays List
            holidays_list = []
            total_sundays = 0
            
            # 1. Global Holidays from resource calendar (Including those without specific calendar)
            global_leaves = self.env['resource.calendar.leaves'].search([
                ('calendar_id', 'in', [calendar.id if calendar else False, False]),
                ('resource_id', '=', False),
                ('date_from', '<', next_month_start_utc),
                ('date_to', '>=', month_start_utc)
            ])
            
            # 2. Custom Public Holidays from ahadu.public.holiday (Ahadu Leave configuration)
            custom_holidays = self.env['ahadu.public.holiday'].search([
                ('date', '>=', month_start),
                ('date', '<', next_month_start)
            ])
            
            # Track holiday dates for heatmap and exclusions
            holiday_dates = set()
            
            for gl in global_leaves:
                h_date = fields.Datetime.context_timestamp(self, gl.date_from).date()
                if month_start <= h_date < next_month_start:
                    et_date_str = ""
                    if EthiopianDateConverter:
                        conv = EthiopianDateConverter()
                        ety, etm, etd = conv.to_ethiopian(h_date.year, h_date.month, h_date.day)
                        et_date_str = f"{etd}/{etm}/{ety}"
                    
                    holidays_list.append({
                        'name': gl.name or 'Public Holiday',
                        'date': h_date.strftime('%d %b'),
                        'et_date': et_date_str,
                        'type': 'holiday'
                    })
                    holiday_dates.add(h_date)

            # 3. Automatic Ethiopian Holidays (New Request)
            # Registry for variable holidays (2024-2026)
            variable_holidays = {
                2024: [
                    (date(2024, 4, 9), "ዒድ አል ፈጥር (Id Al Fitr)"),
                    (date(2024, 5, 3), "ስቅለት (Good Friday)"),
                    (date(2024, 5, 5), "ትንሳኤ (Easter)"),
                    (date(2024, 5, 6), "የትንሳኤ ሰኞ (Easter Monday)"),
                    (date(2024, 6, 17), "ዒድ አል አድሐ - አረፋ (Eid Al Adha)"),
                    (date(2024, 9, 15), "መውሊድ (Mawlid)"),
                ],
                2025: [
                    (date(2025, 3, 30), "ዒድ አል ፈጥር (Id Al Fitr)"),
                    (date(2025, 4, 18), "ስቅለት (Good Friday)"),
                    (date(2025, 4, 20), "ትንሳኤ (Easter)"),
                    (date(2025, 4, 21), "የትንሳኤ ሰኞ (Easter Monday)"),
                    (date(2025, 6, 6), "ዒድ አል አድሐ - አረፋ (Eid Al Adha)"),
                    (date(2025, 9, 4), "መውሊድ (Mawlid)"),
                ],
                2026: [
                    (date(2026, 3, 20), "ዒድ አል ፈጥር (Id Al Fitr)"),
                    (date(2026, 4, 10), "ስቅለት (Good Friday)"),
                    (date(2026, 4, 12), "ትንሳኤ (Easter)"),
                    (date(2026, 4, 13), "የትንሳኤ ሰኞ (Easter Monday)"),
                    (date(2026, 5, 27), "ዒድ አል አድሐ - አረፋ (Eid Al Adha)"),
                    (date(2026, 8, 25), "መውሊድ (Mawlid)"),
                ]
            }
            
            # Fixed Ethiopian Holidays (Fixed in Ethiopian Calendar)
            # Meskerem 1: New Year, Meskerem 17: Meskel, Tahsas 29: Gena, Tir 11: Timket
            # Adwa: March 2 (Gregorian fixed), Patriots: May 5 (Gregorian fixed), Labor: May 1 (Gregorian fixed)
            fixed_ethiopian = [
                (1, 1, "እንቁጣጣሽ (Ethiopian New Year)"),
                (1, 17, "መስቀል (Finding of the True Cross)"),
                (4, 29, "ገና (Ethiopian Christmas)"),
                (5, 11, "ጥምቀት (Ethiopian Epiphany)"),
            ]
            
            # Map fixed Gregorian ones
            gregorian_fixed = [
                (3, 2, "አድዋ (Victory of Adwa)"),
                (5, 1, "የሰራተኞች ቀን (International Labor Day)"),
                (5, 5, "የድል ቀን (Patriots Victory Day)"),
            ]

            # Add fixed gregorian ones
            for m, d, name in gregorian_fixed:
                h_date = date(year, m, d)
                if month_start <= h_date < next_month_start:
                    if h_date not in holiday_dates:
                        et_date_str = ""
                        if EthiopianDateConverter:
                            conv = EthiopianDateConverter()
                            ety, etm, etd = conv.to_ethiopian(h_date.year, h_date.month, h_date.day)
                            et_date_str = f"{etd}/{etm}/{ety}"
                            
                        holidays_list.append({
                            'name': name, 
                            'date': h_date.strftime('%d %b'), 
                            'et_date': et_date_str,
                            'type': 'holiday'
                        })
                        holiday_dates.add(h_date)

            # Add variable registry ones
            if year in variable_holidays:
                for h_date, name in variable_holidays[year]:
                    if month_start <= h_date < next_month_start:
                        if h_date not in holiday_dates:
                            et_date_str = ""
                            if EthiopianDateConverter:
                                conv = EthiopianDateConverter()
                                ety, etm, etd = conv.to_ethiopian(h_date.year, h_date.month, h_date.day)
                                et_date_str = f"{etd}/{etm}/{ety}"
                                
                            holidays_list.append({
                                'name': name, 
                                'date': h_date.strftime('%d %b'), 
                                'et_date': et_date_str,
                                'type': 'holiday'
                            })
                            holiday_dates.add(h_date)

            # Add fixed Ethiopian ones (using converter if available)
            if EthiopianDateConverter:
                conv = EthiopianDateConverter()
                # Check current year and previous year (since ET year overlaps two GR years)
                for et_year in [year - 7, year - 8, year - 9]:
                    for m, d, name in fixed_ethiopian:
                        try:
                            h_date = conv.to_gregorian(et_year, m, d)
                            if month_start <= h_date < next_month_start:
                                if h_date not in holiday_dates:
                                    et_date_str = f"{d}/{m}/{et_year}" # This one we already have et components
                                    holidays_list.append({
                                        'name': name, 
                                        'date': h_date.strftime('%d %b'), 
                                        'et_date': et_date_str,
                                        'type': 'holiday'
                                    })
                                    holiday_dates.add(h_date)
                        except:
                            pass

            for ch in custom_holidays:
                if ch.date not in holiday_dates: # Avoid duplicates
                    et_date_str = ""
                    if EthiopianDateConverter:
                        conv = EthiopianDateConverter()
                        ety, etm, etd = conv.to_ethiopian(ch.date.year, ch.date.month, ch.date.day)
                        et_date_str = f"{etd}/{etm}/{ety}"
                        
                    holidays_list.append({
                        'name': ch.name,
                        'date': ch.date.strftime('%d %b'),
                        'et_date': et_date_str,
                        'type': 'holiday'
                    })
                    holiday_dates.add(ch.date)

            # Ensure scheduled_days excludes these holidays if they were in work_dates
            if work_dates:
                 work_dates = work_dates - holiday_dates
                 scheduled_days = len(work_dates)

            # 3. Sundays
            curr = month_start
            while curr < next_month_start:
                if curr.weekday() == 6: # Sunday
                    total_sundays += 1
                curr += timedelta(days=1)
                
            # Count leaves specifically for days that were scheduled (to avoid overcounting)
            leave_days_count = 0
            for l in all_month_leaves:
                l_start = max(l.request_date_from, month_start)
                l_end = min(l.request_date_to, next_month_start - timedelta(days=1))
                d = l_start
                while d <= l_end:
                    if d in work_dates: # Only count if it was a scheduled workday
                        leave_days_count += 1
                    d += timedelta(days=1)
            
            # Absent calculation: scheduled - (present + leave)
            # We use DISTINT days for attendance to match calendar dots
            query_present_dates = "SELECT DISTINCT(check_in::date) FROM hr_attendance WHERE employee_id = %s AND check_in >= %s AND check_in < %s"
            self.env.cr.execute(query_present_dates, (current_employee.id, month_start, next_month_start))
            present_dates = {r[0] for r in self.env.cr.fetchall()}
            present_days = len(present_dates)

            absent_days_count = scheduled_days - present_days - leave_days_count
            if absent_days_count < 0: absent_days_count = 0

            # Percentage based on scheduled days
            attendance_perc = (present_days / scheduled_days * 100) if scheduled_days > 0 else 0

            summary_data = {
                'present_days': present_days,
                'absent_days': absent_days_count,
                'leave_days': leave_days_count,
                'total_holidays': len(holiday_dates),
                'miss_out_days': miss_out_days,
                'scheduled_days': scheduled_days,
                'attendance_perc': round(attendance_perc, 1),
                'total_sundays': total_sundays,
                'holidays': sorted(holidays_list, key=lambda x: x['date']),
                'current_employee': {'id': current_employee.id, 'name': current_employee.name}
            }
            
            # Generate calendar heatmap
            calendar_heatmap = []
            month_iter_date = month_start
            while month_iter_date < next_month_start:
                day_status = 'not-scheduled'
                tooltip = ''
                is_scheduled = month_iter_date in work_dates
                
                # Filter bulk data
                day_att = all_month_attendances.filtered(lambda a: fields.Datetime.context_timestamp(self, a.check_in).date() == month_iter_date)
                day_leave = all_month_leaves.filtered(lambda l: l.request_date_from <= month_iter_date <= l.request_date_to)
                
                # Check for holiday
                is_holiday = month_iter_date in holiday_dates

                if month_iter_date.weekday() == 6:
                    day_status = 'weekend'
                    tooltip = 'Sunday'
                elif is_holiday:
                    day_status = 'weekend'
                    h_name = next((h['name'] for h in holidays_list if h['date'] == month_iter_date.strftime('%d %b')), 'Public Holiday')
                    tooltip = h_name
                elif day_leave:
                    day_status = 'on-leave'
                    tooltip = f"On Leave ({day_leave[0].holiday_status_id.name})"
                elif day_att:
                    att = day_att[0]
                    if att.attendance_status in ['miss_out', 'late_in_miss_out', 'on_time_miss_out']:
                        day_status = 'critical'
                        tooltip = 'Missed Out'
                    elif att.is_late or att.early_out_minutes > 0:
                        day_status = 'warning'
                        tooltip = 'Late' if att.is_late else 'Early Out'
                    else:
                        day_status = 'good'
                        tooltip = 'On Time'
                elif is_scheduled or month_iter_date.weekday() == 5:
                    if month_iter_date < today:
                        day_status = 'critical'
                        tooltip = 'Absent'
                    else:
                        day_status = 'not-scheduled'
                        tooltip = 'Pending'
                
                calendar_heatmap.append({
                    'date': month_iter_date.day,
                    'full_date': month_iter_date.strftime('%Y-%m-%d'),
                    'status': day_status,
                    'tooltip': tooltip,
                    'is_today': month_iter_date == today
                })
                month_iter_date += timedelta(days=1)
            
            summary_data.update({
                'calendar_heatmap': calendar_heatmap,
                'month_name': month_start.strftime('%B %Y'),
                'month_start_weekday': month_start.weekday(),
                'today_date': today.strftime('%Y-%m-%d')
            })

        return {'kpi_data': kpi_data, 'chart_data': chart_data, 'realtime_logs': log_list, 'summary_data': summary_data, 'uid': self.env.user.id}

  

