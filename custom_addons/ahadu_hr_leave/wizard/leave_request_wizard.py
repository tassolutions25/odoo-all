from ..models import ethiopian_calendar
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, time, timedelta

class LeaveRequestWizard(models.TransientModel):
    _name = 'ahadu.leave.request.wizard'
    _description = 'Unified Leave Request Wizard'

    employee_id = fields.Many2one('hr.employee', string="Employee", readonly=True, default=lambda self: self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1))
    
    # User can select a specific balance (e.g., Annual Leave 2024)
    allocation_id = fields.Many2one(
        'hr.leave.allocation', string="Leave Balance",
        domain="[('employee_id', '=', employee_id), ('state', '=', 'validate'), ('effective_remaining_leaves', '>', 0)]"
    )
    # This field is now the primary driver or is auto-filled
    holiday_status_id = fields.Many2one(
        'hr.leave.type', string="Leave Type", required=True,
    )

    is_half_day = fields.Boolean(string="Half Day")
    half_day_session = fields.Selection([
        ('morning', 'Morning'),
        ('afternoon', 'Afternoon')
    ], string="Session")
    
    # This field is for UX only, to show the user their balance.
    available_days = fields.Float(string="Available Days", readonly=True, digits=(16, 2))
    
    request_date_from = fields.Date(string="Start Date", required=True, default=fields.Date.context_today)
    request_date_to = fields.Date(string="End Date", required=True, default=fields.Date.context_today)
    name = fields.Char(string="Description")
    number_of_days = fields.Float(
        string="Requested (Days)",
        compute="_compute_number_of_days",
        readonly=False)

    is_attachment_mandatory = fields.Boolean(string="Attachment is Mandatory", compute='_compute_is_attachment_mandatory')
    attachment_ids = fields.Many2many('ir.attachment', string="Supporting Document")


    @api.onchange('is_half_day')
    def _onchange_is_half_day(self):
        """
        Automatically defaults the session to Morning when Half Day is checked.
        This satisfies client-side validation instantly and allows the calculation to run.
        """
        if self.is_half_day and not self.half_day_session:
            self.half_day_session = 'morning'


    @api.depends('request_date_from', 'request_date_to', 'employee_id', 'is_half_day')
    def _compute_number_of_days(self):
        """
        Calculates the requested days automatically and triggers an instant 
        UI update when dates, employee, or half-day options are toggled.
        """
        for wizard in self:
            if wizard.request_date_from and wizard.request_date_to and wizard.employee_id:
                from datetime import datetime, time, timedelta
                date_from_dt = datetime.combine(wizard.request_date_from, time.min)
                date_to_dt = datetime.combine(wizard.request_date_to, time.max)
                
                calendar = wizard.employee_id.resource_calendar_id
                
                # Fetch custom public holidays
                public_holidays = self.env['ahadu.public.holiday'].sudo().search([
                    ('date', '>=', wizard.request_date_from),
                    ('date', '<=', wizard.request_date_to)
                ]).mapped('date')
                
                work_hours_by_date = {}
                if calendar:
                    work_time_dict = wizard.employee_id._list_work_time_per_day(date_from_dt, date_to_dt)
                    work_hours_by_date = {day_date: hours for day_date, hours in work_time_dict.get(wizard.employee_id.id, [])}
                    hours_per_day = calendar.hours_per_day or 8.0

                total_days = 0.0
                current_date = wizard.request_date_from
                while current_date <= wizard.request_date_to:
                    if current_date in public_holidays:
                        pass
                    elif current_date.weekday() == 5:  # Saturday
                        total_days += 0.5
                    else:
                        if calendar:
                            hours = work_hours_by_date.get(current_date, 0.0)
                            if hours > 0:
                                if wizard.is_half_day:
                                    total_days += 0.5
                                else:
                                    total_days += min(1.0, hours / hours_per_day) if hours_per_day else 1.0
                        else:
                            if current_date.weekday() != 6:
                                total_days += 0.5 if wizard.is_half_day else 1.0
                    
                    current_date += timedelta(days=1)
                        
                wizard.number_of_days = total_days
            else:
                wizard.number_of_days = 0

    @api.depends('holiday_status_id')
    def _compute_is_attachment_mandatory(self):
        for wizard in self:
            wizard.is_attachment_mandatory = wizard.holiday_status_id.support_document if wizard.holiday_status_id else False

    ethiopian_date_from = fields.Char(string="From (Ethiopian)", compute='_compute_ethiopian_dates', readonly=True)
    ethiopian_date_to = fields.Char(string="To (Ethiopian)", compute='_compute_ethiopian_dates', readonly=True)

    @api.depends('request_date_from', 'request_date_to')
    def _compute_ethiopian_dates(self):
        converter = ethiopian_calendar.EthiopianDateConverter()
        for wizard in self:
            if wizard.request_date_from:
                g_from = wizard.request_date_from
                et_date = converter.to_ethiopian(g_from.year, g_from.month, g_from.day)
                wizard.ethiopian_date_from = f"{et_date[2]} {converter.MONTH_NAMES[et_date[1]]}, {et_date[0]}"
            else:
                wizard.ethiopian_date_from = False

            if wizard.request_date_to:
                g_to = wizard.request_date_to
                et_date = converter.to_ethiopian(g_to.year, g_to.month, g_to.day)
                wizard.ethiopian_date_to = f"{et_date[2]} {converter.MONTH_NAMES[et_date[1]]}, {et_date[0]}"
            else:
                wizard.ethiopian_date_to = False

    @api.onchange('allocation_id')
    def _onchange_allocation_id(self):
        if self.allocation_id:
            self.holiday_status_id = self.allocation_id.holiday_status_id
            self.available_days = self.allocation_id.effective_remaining_leaves
        else:
            self.available_days = 0

    @api.onchange('holiday_status_id')
    def _onchange_holiday_status_id(self):
        if self.holiday_status_id and not self.allocation_id:
            if self.holiday_status_id.requires_allocation == 'yes':
                allocations = self.env['hr.leave.allocation'].search([
                    ('employee_id', '=', self.employee_id.id),
                    ('holiday_status_id', '=', self.holiday_status_id.id),
                    ('state', '=', 'validate'),
                ])
                self.available_days = sum(allocations.mapped('effective_remaining_leaves'))
            else:
                self.available_days = 0

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        res = super(LeaveRequestWizard, self).fields_get(allfields, attributes)
        if 'holiday_status_id' in res:
            allowed_leave_type_ids = self.env['hr.leave.type']._get_contextual_leave_types().ids
            res['holiday_status_id']['domain'] = [('id', 'in', allowed_leave_type_ids)]
        return res

    @api.onchange('request_date_from', 'request_date_to', 'employee_id', 'is_half_day')
    def _onchange_dates(self):
        if self.request_date_from and self.request_date_to and self.employee_id:
            date_from_dt = datetime.combine(self.request_date_from, time.min)
            date_to_dt = datetime.combine(self.request_date_to, time.max)
            calendar = self.employee_id.resource_calendar_id

            # Fetch custom public holidays
            public_holidays = self.env['ahadu.public.holiday'].sudo().search([
                ('date', '>=', self.request_date_from),
                ('date', '<=', self.request_date_to)
            ]).mapped('date')

        #     total_days = 0.0

        #     if calendar:
        #         work_time_dict = self.employee_id._list_work_time_per_day(date_from_dt, date_to_dt)
        #         work_days = work_time_dict.get(self.employee_id.id, [])
        #         hours_per_day = calendar.hours_per_day or 8.0
                
        #         for day_date, hours in work_days:
        #             if day_date in public_holidays:
        #                 continue
                    
        #             # Weekday 5 represents Saturday
        #             if day_date.weekday() == 5:
        #                 total_days += 0.5
        #             else:
        #                 total_days += min(1.0, hours / hours_per_day) if hours_per_day else 1.0
        #     else:
        #         # Fallback calculation without resource calendars
        #         current_date = self.request_date_from
        #         while current_date <= self.request_date_to:
        #             if current_date not in public_holidays:
        #                 if current_date.weekday() == 5:
        #                     total_days += 0.5
        #                 else:
        #                     total_days += 1.0
        #             current_date += timedelta(days=1)
                    
        #     self.number_of_days = total_days
        # else:
        #     self.number_of_days = 0

        # Map work hours per day if calendar is present
            work_hours_by_date = {}
            if calendar:
                work_time_dict = self.employee_id._list_work_time_per_day(date_from_dt, date_to_dt)
                work_hours_by_date = {day_date: hours for day_date, hours in work_time_dict.get(self.employee_id.id, [])}
                hours_per_day = calendar.hours_per_day or 8.0

            total_days = 0.0
            current_date = self.request_date_from
            
            # Step through each day in the request range individually
            while current_date <= self.request_date_to:
                if current_date in public_holidays:
                    # Public Holiday: always 0
                    pass
                elif current_date.weekday() == 5:
                    # Saturday: always counts as 0.5 (even if absent from calendar schedule)
                    total_days += 0.5
                else:
                    # Other days (Mon-Fri, Sun)
                    if calendar:
                        hours = work_hours_by_date.get(current_date, 0.0)
                        if hours > 0:
                            if self.is_half_day:
                                total_days += 0.5
                            else:
                                total_days += min(1.0, hours / hours_per_day) if hours_per_day else 1.0
                    else:
                        # Fallback without calendar: exclude Sundays (6)
                        if current_date.weekday() != 6:
                            total_days += 0.5 if self.is_half_day else 1.0
                
                current_date += timedelta(days=1)
                    
            self.number_of_days = total_days
        else:
            self.number_of_days = 0
            
    def action_submit_request(self):
        self.ensure_one()
        
        leave_type = self.holiday_status_id
        if not leave_type:
            raise UserError(_("You must select a Leave Type."))

        if self.is_half_day and not self.half_day_session:
            raise UserError(_("Please select a session (Morning or Afternoon) for your half-day request."))

        if self.number_of_days <= 0:
            raise UserError(_("The requested leave duration must be positive."))
            
        if self.is_attachment_mandatory and not self.attachment_ids:
            raise UserError(_("You must attach a supporting document for this type of leave."))

        # --- SERVER-SIDE VALIDATION AND LINKING ---
        target_allocation = self.allocation_id

        if leave_type.requires_allocation == 'yes':
            # 1. Verify the balance on the server to prevent errors.
            allocations = self.env['hr.leave.allocation'].search([
                ('employee_id', '=', self.employee_id.id),
                ('holiday_status_id', '=', leave_type.id),
                ('state', '=', 'validate'),
            ])
            available_days_on_server = sum(allocations.mapped('effective_remaining_leaves'))

            if self.number_of_days > available_days_on_server:
                raise ValidationError(_(
                    "You cannot request %.2f days of %s because you only have %.2f days available."
                ) % (self.number_of_days, leave_type.name, available_days_on_server))

            # 2. If no specific allocation was chosen, find the correct one to link to.
            if not target_allocation:
                allocation_to_use = self.env['hr.leave.allocation'].search([
                    ('employee_id', '=', self.employee_id.id),
                    ('holiday_status_id', '=', leave_type.id),
                    ('state', '=', 'validate'),
                    ('effective_remaining_leaves', '>', 0),
                ], order='date_from asc', limit=1)
                
                if not allocation_to_use:
                    raise ValidationError(_("You do not have a valid leave balance for '%s'.") % leave_type.name)
                
                target_allocation = allocation_to_use

        leave_values = {
            'holiday_status_id': leave_type.id,
            'employee_id': self.employee_id.id,
            'request_date_from': self.request_date_from,
            'request_date_to': self.request_date_to,
            'name': self.name,
            # This is the key: we ensure allocation_id is set for all allocated leaves.
            'allocation_id': target_allocation.id if target_allocation else False,
            'is_half_day': self.is_half_day,
            'half_day_session': self.half_day_session if self.is_half_day else False,
        }
        new_leave = self.env['hr.leave'].create(leave_values)

        if self.attachment_ids:
            new_leave.message_post(attachment_ids=self.attachment_ids.ids)

        return {'type': 'ir.actions.act_window_close'}