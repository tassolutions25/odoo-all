# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api
from datetime import datetime, timedelta
import pytz

_logger = logging.getLogger(__name__)


class HrAttendanceODInherit(models.Model):
    _inherit = 'hr.attendance'

    # --- On-Duty Fields ---
    is_od = fields.Boolean(
        string="On Duty", default=False, readonly=True, copy=False,
        help="True if this attendance was auto-generated from an On-Duty request.",
    )
    on_duty_id = fields.Many2one(
        'hr.on.duty', string="On-Duty Request",
        readonly=True, copy=False, ondelete='set null',
    )

    @api.depends('check_in', 'check_out', 'lunch_out', 'lunch_in',
                 'employee_id.attendance_policy_id', 'employee_id.resource_calendar_id')
    def _compute_attendance_analysis(self, employee_tz=False):
        """
        Override to handle On-Duty integration with attendance status.

        Three scenarios handled:
        1. OD-generated records (is_od=True) → force 'on_duty' status
        2. Physical check-ins on a Half Day AM OD day → employee's expected
           start should be the shift midpoint (not 8 AM), so afternoon
           check-in is NOT marked as 'late_in'
        3. Physical check-ins on a Half Day PM OD day → employee's expected
           end should be the shift midpoint (not 5 PM), so noon checkout
           is NOT marked as 'early_out'
        """
        # 1. Separate OD-generated records from physical records
        od_records = self.filtered(lambda a: a.is_od)
        regular_records = self - od_records

        # Process OD-generated records: force on_duty status
        for att in od_records:
            att.is_late = False
            att.late_minutes = 0.0
            att.late_display = ''
            att.late_duration_display = ''
            att.early_out_minutes = 0.0
            att.early_out_duration_display = ''
            att.attendance_status = 'on_duty'

        if not regular_records:
            return

        # 2. Let the parent compute analysis normally first
        super(HrAttendanceODInherit, regular_records)._compute_attendance_analysis(
            employee_tz=employee_tz
        )

        # 3. Post-process: fix status for physical records on OD days
        #    where the standard analysis incorrectly marks late/early
        self._fix_od_half_day_status(regular_records)

    def _fix_od_half_day_status(self, records):
        """
        After standard analysis, check each record for an approved half-day OD.
        If found, recalculate lateness/earliness using the adjusted shift boundary.

        - Half Day AM OD: employee is OD in the morning → expected_start = midpoint
          → An afternoon check-in at 12:30 is NOT late
        - Half Day PM OD: employee is OD in the afternoon → expected_end = midpoint
          → A noon checkout is NOT early
        - Full Day OD: any physical record on that day should be 'on_time'
        """
        OnDuty = self.env['hr.on.duty'].sudo()

        for att in records:
            if not att.employee_id or not att.check_in:
                continue

            # Get local check-in date
            try:
                tz_name = att.employee_id.tz or self.env.user.tz or 'UTC'
                tz = pytz.timezone(tz_name)
            except Exception:
                tz = pytz.utc

            try:
                check_in_local = pytz.utc.localize(att.check_in).astimezone(tz)
            except Exception:
                check_in_local = att.check_in
            target_date = check_in_local.date()

            # Search for approved OD on this day for this employee
            od = OnDuty.search([
                ('employee_id', '=', att.employee_id.id),
                ('state', '=', 'approved'),
                ('date_from', '<=', datetime.combine(target_date, datetime.max.time())),
                ('date_to', '>=', datetime.combine(target_date, datetime.min.time())),
            ], limit=1)

            if not od:
                continue

            # --- Full Day OD: any physical record should be on_time ---
            if od.od_type == 'full_day':
                att.is_late = False
                att.late_minutes = 0.0
                att.late_display = ''
                att.late_duration_display = ''
                att.early_out_minutes = 0.0
                att.early_out_duration_display = ''
                att.attendance_status = 'on_time'
                continue

            # --- Half Day AM OD: employee was OD in the morning ---
            # Their physical check-in is for the afternoon half.
            # Expected start = start of 2nd work interval (after lunch), NOT midpoint.
            if od.od_type == 'half_day_am':
                intervals = self._get_od_work_intervals(att.employee_id, target_date, tz)
                if intervals and len(intervals) >= 2:
                    # Use start of 2nd interval as PM expected start
                    # e.g., [8:00-12:00, 13:00-17:00] → pm_start = 13:00
                    pm_start = intervals[1][0]  # Start of afternoon interval

                    # Get tolerance
                    tolerance_minutes = 15.0
                    calendar = att.employee_id.resource_calendar_id
                    if calendar and hasattr(calendar, 'tolerance_late_check_in'):
                        tolerance_minutes = calendar.tolerance_late_check_in

                    late_threshold = pm_start + timedelta(minutes=tolerance_minutes)

                    if check_in_local <= late_threshold:
                        # NOT late — arrived on time for the PM half
                        att.is_late = False
                        att.late_minutes = 0.0
                        att.late_display = ''
                        att.late_duration_display = ''
                        att.attendance_status = 'on_time'
                    else:
                        # Late, measured from PM start (13:00), not shift start (8:00)
                        lateness_delta = check_in_local - pm_start
                        att.late_minutes = round(lateness_delta.total_seconds() / 60.0, 2)
                        att.late_duration_display = self._format_duration(att.late_minutes)
                        att.late_display = att.late_duration_display
                        att.is_late = True
                        att.attendance_status = 'late_in'
                elif intervals and len(intervals) == 1:
                    # Single interval (no lunch break) — use midpoint as fallback
                    shift_start = intervals[0][0]
                    shift_end = intervals[0][1]
                    shift_duration = (shift_end - shift_start).total_seconds()
                    pm_start = shift_start + timedelta(seconds=shift_duration / 2)

                    tolerance_minutes = 15.0
                    calendar = att.employee_id.resource_calendar_id
                    if calendar and hasattr(calendar, 'tolerance_late_check_in'):
                        tolerance_minutes = calendar.tolerance_late_check_in

                    late_threshold = pm_start + timedelta(minutes=tolerance_minutes)

                    if check_in_local <= late_threshold:
                        att.is_late = False
                        att.late_minutes = 0.0
                        att.late_display = ''
                        att.late_duration_display = ''
                        att.attendance_status = 'on_time'
                    else:
                        lateness_delta = check_in_local - pm_start
                        att.late_minutes = round(lateness_delta.total_seconds() / 60.0, 2)
                        att.late_duration_display = self._format_duration(att.late_minutes)
                        att.late_display = att.late_duration_display
                        att.is_late = True
                        att.attendance_status = 'late_in'

            # --- Half Day PM OD: employee was OD in the afternoon ---
            # Their physical attendance is for the morning half.
            # Expected end = end of 1st work interval (before lunch), NOT midpoint.
            elif od.od_type == 'half_day_pm':
                intervals = self._get_od_work_intervals(att.employee_id, target_date, tz)
                if intervals and att.check_out:
                    # Use end of 1st interval as AM expected end
                    # e.g., [8:00-12:00, 13:00-17:00] → am_end = 12:00
                    am_end = intervals[0][1]  # End of morning interval

                    try:
                        check_out_local = pytz.utc.localize(att.check_out).astimezone(tz)
                    except Exception:
                        check_out_local = att.check_out

                    early_threshold = am_end - timedelta(minutes=5)

                    if check_out_local >= early_threshold:
                        # NOT early — left on time for the AM half
                        att.early_out_minutes = 0.0
                        att.early_out_duration_display = ''
                        if att.attendance_status in ('late_in_early_out',):
                            att.attendance_status = 'late_in' if att.is_late else 'on_time'
                        elif att.attendance_status == 'early_out':
                            att.attendance_status = 'on_time'
                    else:
                        # Early out, measured from AM end (12:00)
                        earliness_delta = am_end - check_out_local
                        att.early_out_minutes = round(earliness_delta.total_seconds() / 60.0, 2)
                        att.early_out_duration_display = self._format_duration(att.early_out_minutes)

            # --- Hourly OD ---
            # For hourly OD, the physical check-in might still be outside OD hours.
            # We check if the check-in falls within the OD period and adjust.
            elif od.od_type == 'hourly':
                od_start = od.date_from
                od_end = od.date_to
                # If the check-in is within the OD window, it's on_time
                if od_start <= att.check_in <= od_end:
                    att.is_late = False
                    att.late_minutes = 0.0
                    att.late_display = ''
                    att.late_duration_display = ''
                    att.attendance_status = 'on_time'

    def _get_od_work_intervals(self, employee, target_date, tz):
        """
        Get the actual work intervals for the employee on a given date.
        Returns a list of (start_datetime, end_datetime) tuples.
        e.g., [(8:00, 12:00), (13:00, 17:00)] for a schedule with lunch break.
        This is critical for Half Day OD logic — we need the real interval
        boundaries, not a mathematical midpoint.
        """
        from datetime import time as dt_time
        try:
            # 1. Check assigned shift schedule
            shift = self.env['ab.hr.shift.schedule'].search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'assigned'),
                ('date_start', '<=', datetime.combine(target_date, dt_time(23, 59))),
                ('date_end', '>=', datetime.combine(target_date, dt_time(0, 0))),
            ], limit=1)

            calendar = False
            if shift and shift.shift_type_id.resource_calendar_id:
                calendar = shift.shift_type_id.resource_calendar_id
            elif hasattr(employee, 'attendance_policy_id') and employee.attendance_policy_id and employee.attendance_policy_id.resource_calendar_id:
                calendar = employee.attendance_policy_id.resource_calendar_id
            elif employee.resource_calendar_id:
                calendar = employee.resource_calendar_id

            if calendar:
                day_start = tz.localize(datetime.combine(target_date, dt_time(0, 0)))
                day_end = tz.localize(datetime.combine(target_date, dt_time(23, 59, 59)))
                intervals_dict = calendar._work_intervals_batch(
                    day_start, day_end,
                    resources=employee.resource_id, tz=tz,
                )
                employee_intervals = list(intervals_dict.get(employee.resource_id.id, []))
                if employee_intervals:
                    # Return list of (start, end) tuples
                    return [(iv[0], iv[1]) for iv in employee_intervals]

            # Fallback: standard schedule (no lunch info available)
            if target_date.weekday() == 5:  # Saturday
                start_t, end_t = dt_time(8, 0), dt_time(12, 0)
                return [(tz.localize(datetime.combine(target_date, start_t)),
                         tz.localize(datetime.combine(target_date, end_t)))]
            elif target_date.weekday() == 6:  # Sunday
                return []
            else:
                # Mon-Fri: use standard 8-12, 13-17 with lunch break
                return [
                    (tz.localize(datetime.combine(target_date, dt_time(8, 0))),
                     tz.localize(datetime.combine(target_date, dt_time(12, 0)))),
                    (tz.localize(datetime.combine(target_date, dt_time(13, 0))),
                     tz.localize(datetime.combine(target_date, dt_time(17, 0)))),
                ]
        except Exception as e:
            _logger.warning("Could not get work intervals for OD adjustment: %s", e)
            return []

    def _check_validity(self):
        """
        Override to skip the overlapping attendance check for OD records.
        This prevents 'Double Attendance' errors when a physical check-in
        coexists with an OD virtual log.
        """
        # Only validate non-OD records
        non_od_records = self.filtered(lambda a: not a.is_od)
        if non_od_records:
            return super(HrAttendanceODInherit, non_od_records)._check_validity()
        return True
