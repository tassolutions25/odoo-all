# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, time, timedelta
import pytz

_logger = logging.getLogger(__name__)


class HrOnDuty(models.Model):
    _name = 'hr.on.duty'
    _description = 'On-Duty Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'name'

    # ===================================================================
    #  FIELD DEFINITIONS
    # ===================================================================
    name = fields.Char(
        string="Reference", readonly=True, copy=False,
        default=lambda self: _('New'),
    )
    employee_id = fields.Many2one(
        'hr.employee', string="Employee", required=True,
        default=lambda self: self.env.user.employee_id,
        tracking=True,
    )
    department_id = fields.Many2one(
        'hr.department', string="Department",
        related='employee_id.department_id', store=True, readonly=True,
    )
    manager_id = fields.Many2one(
        'hr.employee', string="Manager",
        related='employee_id.parent_id', store=True, readonly=True,
    )
    company_id = fields.Many2one(
        'res.company', string="Company",
        default=lambda self: self.env.company, readonly=True,
    )

    # --- OD Type & Duration ---
    od_type = fields.Selection([
        ('full_day', 'Full Day'),
        ('half_day_am', 'Half Day (AM)'),
        ('half_day_pm', 'Half Day (PM)'),
        ('hourly', 'Hourly'),
    ], string="OD Type", required=True, default='full_day', tracking=True)

    date_from = fields.Datetime(string="From", required=True, tracking=True)
    date_to = fields.Datetime(string="To", required=True, tracking=True)
    total_hours = fields.Float(
        string="Total Hours", compute='_compute_total_hours', store=True,
    )

    # --- Reason & Compliance ---
    reason_type = fields.Selection([
        ('client_visit', 'Client Visit'),
        ('audit', 'Audit'),
        ('training', 'Training'),
        ('regulatory_meeting', 'Regulatory Meeting'),
        ('other', 'Other'),
    ], string="Reason Type", required=True, tracking=True)

    description = fields.Text(string="Description / Justification", required=True)
    attachment = fields.Binary(string="Supporting Document")
    attachment_filename = fields.Char(string="Attachment Filename")
    gps_coordinates = fields.Char(
        string="GPS Coordinates",
        help="Latitude, Longitude from mobile check-in",
    )

    # --- Workflow ---
    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting_manager', 'Waiting Manager'),
        ('waiting_hr', 'Waiting HR'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string="Status", default='draft', tracking=True, copy=False)

    attendance_created = fields.Boolean(
        string="Attendance Created", default=False, copy=False,
        help="True if virtual attendance logs were generated for this OD.",
    )

    # --- Approval tracking ---
    manager_approved_by = fields.Many2one(
        'res.users', string="Manager Approved By", readonly=True, copy=False,
    )
    manager_approved_date = fields.Datetime(
        string="Manager Approval Date", readonly=True, copy=False,
    )
    hr_approved_by = fields.Many2one(
        'res.users', string="HR Approved By", readonly=True, copy=False,
    )
    hr_approved_date = fields.Datetime(
        string="HR Approval Date", readonly=True, copy=False,
    )
    rejected_by = fields.Many2one(
        'res.users', string="Rejected By", readonly=True, copy=False,
    )
    rejection_reason = fields.Text(string="Rejection Reason", copy=False)

    # ===================================================================
    #  COMPUTED FIELDS
    # ===================================================================
    @api.depends('date_from', 'date_to')
    def _compute_total_hours(self):
        for rec in self:
            if rec.date_from and rec.date_to:
                delta = rec.date_to - rec.date_from
                rec.total_hours = round(delta.total_seconds() / 3600.0, 2)
            else:
                rec.total_hours = 0.0

    # ===================================================================
    #  CONSTRAINTS
    # ===================================================================
    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from >= rec.date_to:
                raise ValidationError(_("'Date To' must be after 'Date From'."))

    @api.constrains('date_from', 'date_to', 'employee_id')
    def _check_leave_overlap(self):
        """Prevent OD requests if an approved Leave exists for the same period."""
        for rec in self:
            if not rec.employee_id or not rec.date_from or not rec.date_to:
                continue
            overlapping_leave = self.env['hr.leave'].search([
                ('employee_id', '=', rec.employee_id.id),
                ('state', '=', 'validate'),
                ('date_from', '<', rec.date_to),
                ('date_to', '>', rec.date_from),
            ], limit=1)
            if overlapping_leave:
                raise ValidationError(_(
                    "Cannot create On-Duty request: Employee '%s' already has an "
                    "approved leave from %s to %s.",
                    rec.employee_id.name,
                    overlapping_leave.date_from,
                    overlapping_leave.date_to,
                ))

    @api.constrains('date_from', 'date_to', 'employee_id')
    def _check_od_overlap(self):
        """Prevent duplicate OD requests for the same period."""
        for rec in self:
            if not rec.employee_id or not rec.date_from or not rec.date_to:
                continue
            domain = [
                ('employee_id', '=', rec.employee_id.id),
                ('state', 'not in', ['rejected']),
                ('date_from', '<', rec.date_to),
                ('date_to', '>', rec.date_from),
                ('id', '!=', rec.id),
            ]
            if self.search_count(domain) > 0:
                raise ValidationError(_(
                    "An On-Duty request already exists for this period."
                ))

    # ===================================================================
    #  ORM OVERRIDES
    # ===================================================================
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.on.duty') or _('New')
        return super().create(vals_list)

    def unlink(self):
        for rec in self:
            if rec.state not in ('draft', 'rejected'):
                raise UserError(_("You can only delete requests in 'Draft' or 'Rejected' status."))
        return super().unlink()

    # ===================================================================
    #  WORKFLOW ACTIONS
    # ===================================================================
    def action_submit(self):
        """Employee submits the request → Waiting Manager."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only draft requests can be submitted."))
            rec.write({'state': 'waiting_manager'})
            rec._send_notification('manager')
        return True

    def action_manager_approve(self):
        """Manager or Super Admin approves → Approved directly."""
        for rec in self:
            if rec.state != 'waiting_manager':
                raise UserError(_("This request is not awaiting manager approval."))
            
            # Ensure the user is the actual manager or an administrator
            if not self.env.user.has_group('base.group_system') and not self.env.user.has_group('ahadu_attendance.group_ahadu_attendance_hr_admin'):
                if rec.employee_id.parent_id.user_id != self.env.user:
                    raise UserError(_("Only the employee's direct manager or an Administrator can approve this request."))
                    
            # Banking Rule: Client Visit requires attachment
            if rec.reason_type == 'client_visit' and not rec.attachment:
                raise UserError(_(
                    "A supporting document is required for 'Client Visit' "
                    "requests before approval."
                ))
            rec.write({
                'state': 'approved',
                'manager_approved_by': self.env.uid,
                'manager_approved_date': fields.Datetime.now(),
            })
            # Create virtual attendance logs upon approval
            rec._create_attendance_records()
            rec._send_notification('approved')
        return True

    def action_hr_approve(self):
        """HR approves → Approved. Creates virtual attendance records."""
        for rec in self:
            if rec.state != 'waiting_hr':
                raise UserError(_("This request is not awaiting HR approval."))
            # Banking Rule: Client Visit requires attachment
            if rec.reason_type == 'client_visit' and not rec.attachment:
                raise UserError(_(
                    "A supporting document is required for 'Client Visit' "
                    "requests before HR can approve."
                ))
            rec.write({
                'state': 'approved',
                'hr_approved_by': self.env.uid,
                'hr_approved_date': fields.Datetime.now(),
            })
            # Create virtual attendance logs upon approval
            rec._create_attendance_records()
            rec._send_notification('approved')
        return True

    def action_reject(self):
        """Manager or HR rejects the request."""
        for rec in self:
            if rec.state not in ('waiting_manager', 'waiting_hr'):
                raise UserError(_("Only pending requests can be rejected."))
            
            # Ensure the user is the actual manager or an administrator
            if not self.env.user.has_group('base.group_system') and not self.env.user.has_group('ahadu_attendance.group_ahadu_attendance_hr_admin'):
                if rec.employee_id.parent_id.user_id != self.env.user:
                    raise UserError(_("Only the employee's direct manager or an Administrator can reject this request."))
                    
            # If attendance was already created (edge case), remove it
            if rec.attendance_created:
                rec._remove_attendance_records()
            rec.write({
                'state': 'rejected',
                'rejected_by': self.env.uid,
            })
            rec._send_notification('rejected')
        return True

    def action_reset_draft(self):
        """Reset a rejected request back to draft."""
        for rec in self:
            if rec.state != 'rejected':
                raise UserError(_("Only rejected requests can be reset to draft."))
            if rec.attendance_created:
                rec._remove_attendance_records()
            rec.write({
                'state': 'draft',
                'manager_approved_by': False,
                'manager_approved_date': False,
                'hr_approved_by': False,
                'hr_approved_date': False,
                'rejected_by': False,
                'rejection_reason': False,
            })
        return True

    # ===================================================================
    #  ATTENDANCE CREATION LOGIC
    # ===================================================================
    def _get_employee_tz(self):
        """Get employee timezone as pytz object."""
        self.ensure_one()
        tz_name = self.employee_id.tz or self.env.user.tz or 'UTC'
        try:
            return pytz.timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            _logger.warning("Unknown timezone '%s', falling back to UTC.", tz_name)
            return pytz.utc

    def _get_shift_times(self, target_date):
        """
        Get expected shift start/end for the employee on a given date.
        Uses the same logic as ahadu_attendance: Shift → Policy → Calendar → Fallback.
        """
        self.ensure_one()
        employee = self.employee_id
        tz = self._get_employee_tz()

        # 1. Check assigned shift schedule
        shift = self.env['ab.hr.shift.schedule'].search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'assigned'),
            ('date_start', '<=', datetime.combine(target_date, time(23, 59))),
            ('date_end', '>=', datetime.combine(target_date, time(0, 0))),
        ], limit=1)

        calendar = False
        if shift and shift.shift_type_id.resource_calendar_id:
            calendar = shift.shift_type_id.resource_calendar_id
        elif employee.attendance_policy_id and employee.attendance_policy_id.resource_calendar_id:
            calendar = employee.attendance_policy_id.resource_calendar_id
        elif employee.resource_calendar_id:
            calendar = employee.resource_calendar_id

        if calendar:
            day_start = tz.localize(datetime.combine(target_date, time(0, 0)))
            day_end = tz.localize(datetime.combine(target_date, time(23, 59, 59)))
            intervals = calendar._work_intervals_batch(
                day_start, day_end,
                resources=employee.resource_id, tz=tz,
            )
            employee_intervals = list(intervals.get(employee.resource_id.id, []))
            if employee_intervals:
                return employee_intervals[0][0], employee_intervals[-1][1]

        # Fallback: Sat 8-12, Mon-Fri 8-17
        if target_date.weekday() == 5:  # Saturday
            start_t, end_t = time(8, 0), time(12, 0)
        elif target_date.weekday() == 6:  # Sunday
            return None, None
        else:
            start_t, end_t = time(8, 0), time(17, 0)

        return (
            tz.localize(datetime.combine(target_date, start_t)),
            tz.localize(datetime.combine(target_date, end_t)),
        )

    def _create_attendance_records(self):
        """Create virtual hr.attendance records based on OD type."""
        Attendance = self.env['hr.attendance'].sudo()
        for rec in self:
            if rec.attendance_created:
                continue

            tz = rec._get_employee_tz()

            if rec.od_type == 'full_day':
                rec._create_full_day_attendance(Attendance, tz)
            elif rec.od_type == 'half_day_am':
                rec._create_half_day_am_attendance(Attendance, tz)
            elif rec.od_type == 'half_day_pm':
                rec._create_half_day_pm_attendance(Attendance, tz)
            elif rec.od_type == 'hourly':
                rec._create_hourly_attendance(Attendance, tz)

            rec.attendance_created = True
            _logger.info(
                "On-Duty %s: Created virtual attendance for employee %s (%s)",
                rec.name, rec.employee_id.name, rec.od_type,
            )

    def _create_full_day_attendance(self, Attendance, tz):
        """Scenario A: Full Day OD → Create attendance matching shift hours."""
        self.ensure_one()
        # Iterate each day in the OD range
        current_date = self.date_from.date()
        end_date = self.date_to.date()

        while current_date <= end_date:
            shift_start, shift_end = self._get_shift_times(current_date)
            if shift_start and shift_end:
                # Convert to UTC for storage
                check_in_utc = shift_start.astimezone(pytz.utc).replace(tzinfo=None)
                check_out_utc = shift_end.astimezone(pytz.utc).replace(tzinfo=None)
                Attendance.create({
                    'employee_id': self.employee_id.id,
                    'check_in': check_in_utc,
                    'check_out': check_out_utc,
                    'check_in_method': 'System',
                    'check_out_method': 'System',
                    'is_od': True,
                    'on_duty_id': self.id,
                })
            current_date += timedelta(days=1)

    def _create_half_day_am_attendance(self, Attendance, tz):
        """Scenario B (AM): Create virtual log from shift start to mid-day."""
        self.ensure_one()
        current_date = self.date_from.date()
        end_date = self.date_to.date()

        while current_date <= end_date:
            shift_start, shift_end = self._get_shift_times(current_date)
            if shift_start and shift_end:
                # Mid-day = midpoint of shift
                shift_duration = (shift_end - shift_start).total_seconds()
                mid_day = shift_start + timedelta(seconds=shift_duration / 2)

                check_in_utc = shift_start.astimezone(pytz.utc).replace(tzinfo=None)
                check_out_utc = mid_day.astimezone(pytz.utc).replace(tzinfo=None)
                Attendance.create({
                    'employee_id': self.employee_id.id,
                    'check_in': check_in_utc,
                    'check_out': check_out_utc,
                    'check_in_method': 'System',
                    'check_out_method': 'System',
                    'is_od': True,
                    'on_duty_id': self.id,
                })
            current_date += timedelta(days=1)

    def _create_half_day_pm_attendance(self, Attendance, tz):
        """Scenario B (PM): Create virtual log from mid-day to shift end."""
        self.ensure_one()
        current_date = self.date_from.date()
        end_date = self.date_to.date()

        while current_date <= end_date:
            shift_start, shift_end = self._get_shift_times(current_date)
            if shift_start and shift_end:
                shift_duration = (shift_end - shift_start).total_seconds()
                mid_day = shift_start + timedelta(seconds=shift_duration / 2)

                check_in_utc = mid_day.astimezone(pytz.utc).replace(tzinfo=None)
                check_out_utc = shift_end.astimezone(pytz.utc).replace(tzinfo=None)
                Attendance.create({
                    'employee_id': self.employee_id.id,
                    'check_in': check_in_utc,
                    'check_out': check_out_utc,
                    'check_in_method': 'System',
                    'check_out_method': 'System',
                    'is_od': True,
                    'on_duty_id': self.id,
                })
            current_date += timedelta(days=1)

    def _create_hourly_attendance(self, Attendance, tz):
        """Scenario C: Hourly OD → Create attendance for exact OD hours."""
        self.ensure_one()
        check_in_utc = self.date_from
        check_out_utc = self.date_to
        Attendance.create({
            'employee_id': self.employee_id.id,
            'check_in': check_in_utc,
            'check_out': check_out_utc,
            'check_in_method': 'System',
            'check_out_method': 'System',
            'is_od': True,
            'on_duty_id': self.id,
        })

    def _remove_attendance_records(self):
        """Remove virtual attendance records created by this OD."""
        for rec in self:
            attendances = self.env['hr.attendance'].sudo().search([
                ('on_duty_id', '=', rec.id),
                ('is_od', '=', True),
            ])
            if attendances:
                attendances.unlink()
                _logger.info(
                    "On-Duty %s: Removed %d virtual attendance records.",
                    rec.name, len(attendances),
                )
            rec.attendance_created = False

    # ===================================================================
    #  NOTIFICATION HELPERS
    # ===================================================================
    def _send_notification(self, notif_type):
        """Send email notification based on workflow step."""
        self.ensure_one()
        template = False
        try:
            if notif_type == 'manager':
                template = self.env.ref('ahadu_on_duty.email_template_od_manager_approval')
            elif notif_type == 'hr':
                template = self.env.ref('ahadu_on_duty.email_template_od_hr_approval')
            elif notif_type in ('approved', 'rejected'):
                template = self.env.ref('ahadu_on_duty.email_template_od_status_update')
        except ValueError:
            _logger.warning("On-Duty email template not found for type: %s", notif_type)
            return

        if template:
            try:
                template.send_mail(self.id, force_send=False)
            except Exception as e:
                _logger.warning("Failed to send On-Duty notification: %s", e)
