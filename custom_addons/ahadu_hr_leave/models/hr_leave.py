import logging
from . import ethiopian_calendar
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)

class HrLeave(models.Model):
    _inherit = 'hr.leave' 

    is_half_day = fields.Boolean(string="Half Day Request")

    can_partial_cancel = fields.Boolean(
        string="Can be Partially Canceled",
        compute='_compute_can_partial_cancel',
    )

    # state = fields.Selection(selection_add=[
    #     ('to_cancel', 'To Cancel')
    # ], ondelete={'to_cancel': 'cascade'})
    state = fields.Selection(selection_add=[
        ('to_cancel', 'To Cancel'),
        ('to_cancel_partially', 'To Partially Cancel')
    ], ondelete={'to_cancel': 'cascade', 'to_cancel_partially': 'cascade'})

    # 2. ADD NEW FIELDS to store the pending change information
    new_end_date_pending = fields.Date(string="Pending New End Date", readonly=True, copy=False)
    partial_cancel_reason = fields.Text(string="Reason for Partial Cancellation", readonly=True, copy=False)
    full_cancel_reason = fields.Text(string="Reason for Full Cancellation", readonly=True, copy=False)

    # --- 3. NEW Partial Cancellation Approval Methods ---

    def _check_approval_hierarchy(self, action_type="approve"):
        """
        Enforces hierarchical approval:
        1. Prevents self-approval.
        2. Ensures current user is the requester's manager.
        3. If no manager (CEO), fallback to Leave Officer.
        """
        for leave in self:
            user = self.env.user
            employee = leave.employee_id
            manager = employee.parent_id
            
            # Administrators can bypass hierarchy if necessary (standard Odoo behavior), 
            # but we still block self-approval for them unless they are the CEO? 
            # Actually, let's stick to the user's strict requirement.
            
            # 1. Self-approval check (Strict)
            if employee.user_id == user:
                raise UserError(_("You cannot %s your own leave request. It must be %sd by your direct manager.") % (action_type, action_type))

            # 2. Hierarchy Check
            if manager:
                # If there is a manager, ONLY that manager's user can approve
                if manager.user_id != user:
                    raise UserError(_(
                        "This leave request for %s must be %sd by their direct manager (%s)."
                    ) % (employee.name, action_type, manager.name))
            else:
                # 3. CEO Level Fallback (No manager defined)
                # Only Leave Officer (HR Personnel) can approve for the CEO
                is_leave_officer = user.has_group('ahadu_hr_leave.group_leave_officer')
                if not is_leave_officer:
                    raise UserError(_("Leave requests for employees without a defined manager (CEO level) must be approved by the HR Leave Officer."))

    def action_approve_partial_cancel(self):
        """ Manager's action to approve a partial cancellation request. """
        self._check_approval_hierarchy(action_type="approve partial cancellation for")
        for leave in self:
            original_days = leave.number_of_days
            original_end_date = leave.request_date_to
            new_end_date = leave.new_end_date_pending
            reason = leave.partial_cancel_reason

            # Use the logic from your old wizard: refuse, reset, write, re-approve
            leave.action_refuse()
            leave.action_reset_confirm() 
            leave.write({
                'request_date_to': new_end_date,
                'name': f"{leave.name or leave.holiday_status_id.name} (Partially Cancelled)",
            })
            # leave.action_confirm()
            leave.action_approve()
            if leave.state != 'validate':
                leave.action_validate()

            # Post the audit message
            new_days = leave.number_of_days
            days_refunded = original_days - new_days
            leave.message_post(body=_(
                "<strong>Partial Cancellation Approved</strong><br/>"
                "The leave end date has been changed from %s to %s.<br/>"
                "Days Refunded to Balance: <strong>%.2f</strong><br/>"
                "<strong>Reason:</strong> %s"
            ) % (original_end_date.strftime('%d %b %Y'), new_end_date.strftime('%d %b %Y'), days_refunded, reason))
    
    def action_reject_partial_cancel(self):
        """ Manager's action to reject a partial cancellation request. """
        self.write({'state': 'validate'})
        self.message_post(body=_("The request to partially cancel this leave has been rejected."))


    def action_withdraw(self):
        """ Allows an employee to withdraw their own request if it is 'To Approve'. """
        for leave in self:
            if leave.state != 'confirm':
                continue
            # Ensure only the employee or an HR manager can withdraw
            if self.env.user != leave.employee_id.user_id and not self.env.user.has_group('hr_holidays.group_hr_holidays_manager'):
                raise UserError(_("You can only withdraw your own leave requests."))
            leave.write({'state': 'draft'})
            leave.message_post(body=_("Leave request withdrawn by the employee."))

    def action_request_cancel(self):
        """ Allows an employee to request cancellation for an 'Approved' leave. """
        for leave in self:
            if leave.state != 'validate':
                continue
            if self.env.user != leave.employee_id.user_id and not self.env.user.has_group('hr_holidays.group_hr_holidays_manager'):
                raise UserError(_("You can only request cancellation for your own leave requests."))
            leave.sudo().write({'state': 'to_cancel'})
            leave.message_post(body=_("Employee has requested to cancel this approved leave."))

    def action_approve_cancel(self):
        self._check_approval_hierarchy(action_type="approve cancellation for")
        for leave in self:
            reason = self.full_cancel_reason
        self.write({'state': 'refuse'})
        self.message_post(body=_(
            "<strong>The request to cancel this leave has been approved.</strong><br/>"
            "<strong>Original Reason:</strong> %s"
        ) % (reason))

    def action_reject_cancel(self):
        """ Manager's action to reject a cancellation request. """
        # This moves the leave back to the 'validate' (Approved) state.
        self.write({'state': 'validate'})
        self.message_post(body=_("The request to cancel this leave has been rejected."))


    @api.depends('state', 'request_date_to')
    def _compute_can_partial_cancel(self):
        """
        This method determines if the 'Partial Cancel' button should be visible.
        The logic is now robustly handled on the server.
        """
        today = fields.Date.context_today(self)
        for leave in self:
            # The button is visible ONLY if the leave is approved AND its end date is today or in the future.
            if leave.state == 'validate' and leave.request_date_to and leave.request_date_to >= today:
                leave.can_partial_cancel = True
            else:
                leave.can_partial_cancel = False

    sick_leave_pay_tier = fields.Selection([
        ('100', '100% Paid'),
        ('50', '50% Paid'),
        ('0', 'Unpaid'),
    ], string="Sick Leave Pay Tier", readonly=True, copy=False, tracking=True)

    # Technical field for CEO approval on LWOP
    ceo_approved = fields.Boolean(string="CEO Approved", copy=False, tracking=True)

    ethiopian_date_from = fields.Char(
        string="From (Ethiopian)",
        compute='_compute_ethiopian_dates',
        store=False,
    )
    
    ethiopian_date_to = fields.Char(
        string="To (Ethiopian)",
        compute='_compute_ethiopian_dates',
        store=False,
    )
    
    allocation_id = fields.Many2one(
        'hr.leave.allocation',
        string="Leave Balance",
        help="Select the specific leave balance you want to use."
    )

    # --- to manage the dynamic workflow ---
    next_approver_id = fields.Many2one(
        'res.users',
        string="Next Approver",
        copy=False,
        help="The user responsible for the next approval step in a dynamic workflow."
    )


    def _recompute_allocation_balances(self):
        """
        Finds all allocations related to the leaves in this recordset and
        forces them to recompute their taken and remaining days.
        This is the key to fixing the balance update issue.
        """
        for leave in self:
            allocations = self.env['hr.leave.allocation'].search([
                ('employee_id', '=', leave.employee_id.id),
                ('holiday_status_id', '=', leave.holiday_status_id.id),
                ('state', '=', 'validate')
            ])
            # Triggering the recompute on the allocation records
            if allocations:
                allocations._compute_leaves()
                allocations._compute_effective_remaining_leaves()


    
    # --- NEW PROBATION VALIDATION METHOD ---
    def _check_probation_period(self):
        """
        Validates that an annual leave request does not fall within the
        employee's 60-day probation period.
        """
        annual_leave_type = self.env.ref('ahadu_hr_leave.ahadu_leave_type_annual', raise_if_not_found=False)
        if not annual_leave_type:
            return # If the leave type isn't configured, we can't check it.

        for leave in self:
            # This rule only applies to the "Annual Leave" type
            if leave.holiday_status_id.id != annual_leave_type.id:
                continue

            employee = leave.employee_id
            if not employee or not employee.date_of_joining:
                continue # Cannot check if there's no joining date.

            # Calculate the end of the probation period (DOJ + 60 calendar days)
            probation_end_date = employee.date_of_joining + relativedelta(days=60)
            
            # Check if the requested leave START date is within the probation period
            if leave.request_date_from < probation_end_date:
                raise ValidationError(_(
                    "Annual leave cannot be taken during the 60-day probation period. "
                    "Your probation ends on %s. Please select a date after this."
                ) % probation_end_date.strftime('%B %d, %Y'))

    @api.constrains('holiday_status_id', 'employee_id')
    def _check_lwop_annual_leave_balance(self):
        """ Validation: Prevent taking LWOP if employee has a positive Annual Leave balance. """
        lwop_type = self.env.ref('ahadu_hr_leave.ahadu_leave_type_lwop', raise_if_not_found=False)
        annual_leave_type = self.env.ref('ahadu_hr_leave.ahadu_leave_type_annual', raise_if_not_found=False)
        if not lwop_type or not annual_leave_type:
            return

        for leave in self.filtered(lambda l: l.holiday_status_id == lwop_type):
            domain = [
                ('employee_id', '=', leave.employee_id.id),
                ('holiday_status_id', '=', annual_leave_type.id),
                ('state', '=', 'validate'),
            ]
            allocations = self.env['hr.leave.allocation'].search(domain)
            if sum(allocations.mapped('effective_remaining_leaves')) > 0:
                raise ValidationError(_("Leave Without Pay cannot be requested while you still have a positive Annual Leave balance."))

    
    @api.depends('request_date_from', 'request_date_to')
    def _compute_ethiopian_dates(self):
        """
        Computes the Ethiopian date representation for the start and end dates.
        """
        converter = ethiopian_calendar.EthiopianDateConverter()
        for leave in self:
            if leave.request_date_from:
                g_from = leave.request_date_from
                # The method returns a tuple (year, month, day)
                et_date = converter.to_ethiopian(g_from.year, g_from.month, g_from.day)
                # We can now safely access the elements by index
                leave.ethiopian_date_from = f"{et_date[2]} {converter.MONTH_NAMES[et_date[1]]}, {et_date[0]}"
            else:
                leave.ethiopian_date_from = False

            if leave.request_date_to:
                g_to = leave.request_date_to
                et_date = converter.to_ethiopian(g_to.year, g_to.month, g_to.day)
                leave.ethiopian_date_to = f"{et_date[2]} {converter.MONTH_NAMES[et_date[1]]}, {et_date[0]}"
            else:
                leave.ethiopian_date_to = False

                
    def _check_medical_certificate(self):
        sick_leave_type = self.env.ref('ahadu_hr_leave.ahadu_sick_leave_request', raise_if_not_found=False)
        for leave in self:
            # Check if the leave is of type "Sick Leave"
            if leave.holiday_status_id.id == sick_leave_type.id and leave.message_attachment_count == 0:
                raise ValidationError(_(
                    "A supporting document (e.g., medical certificate) is required to approve this sick leave request. "
                    "Please ask the employee to use the 'Attach a file' option in the chatter below."
                ))


    @api.depends('holiday_status_id', 'employee_id')
    
    def _check_document_and_reason(self):
        """
        Checks for supporting documents for Sick and Maternity leave.
        """
        sick_type = self.env.ref('ahadu_hr_leave.ahadu_sick_leave_request', raise_if_not_found=False)
        maternity_type = self.env.ref('ahadu_hr_leave.ahadu_leave_type_maternity', raise_if_not_found=False)
        
        for leave in self:
            is_sick = leave.holiday_status_id == sick_type
            is_maternity = leave.holiday_status_id == maternity_type

            if (is_sick or is_maternity) and leave.message_attachment_count == 0:
                raise ValidationError(_(
                    "A supporting document is required to approve this leave request. "
                    "Please use the 'Attach a file' option in the chatter below."
                ))
            
            if is_maternity and not leave.name:
                raise ValidationError(_("Please provide a reason or description for your Maternity Leave request."))

    def _check_maternity_leave_rules(self):
        """
        No longer enforces due date or pregnancy grouping. 
        Maternity leave is now managed via the 1-year replenishment logic.
        """
        pass

    
    def action_confirm(self):
        """
        Override the Submit action to implement a dynamic approval workflow
        for Leave Without Pay based on the request duration.
        """
        lwop_type = self.env.ref('ahadu_hr_leave.ahadu_leave_type_lwop', raise_if_not_found=False)
        
        for leave in self:
            # --- DYNAMIC WORKFLOW LOGIC ---
            if leave.holiday_status_id == lwop_type:
                next_approver = None
                
                # All LWOP requests now route directly to the CEO
                notification_group = self.env.ref('ahadu_hr_leave.group_leave_approver_ceo', raise_if_not_found=False)
                if notification_group:
                    # Find the first user in this group to assign as the next approver
                    next_approver = notification_group.users[:1]
                    _logger.info(f"LWOP request detected. Routing directly to CEO.")

                # If we found a specific approver/group, update the record and notify them
                if next_approver:
                    leave.write({'next_approver_id': next_approver.id})
                    # Post a message in the chatter, tagging the responsible group
                    leave.message_post(
                        body=_(
                            "This Leave Without Pay request requires approval from the %s group."
                        ) % (notification_group.name),
                        partner_ids=notification_group.users.partner_id.ids
                    )
        
        # Finally, call the original Odoo 'confirm' method to move the state to "To Approve"
        return super(HrLeave, self).action_confirm()



    def action_approve(self):
        """ Override Approve to handle the special LWOP workflow and hierarchy checks. """
        self._check_approval_hierarchy(action_type="approve")
        
        lwop_type = self.env.ref('ahadu_hr_leave.ahadu_leave_type_lwop', raise_if_not_found=False)
        # leave_officer_group = self.env.ref('ahadu_hr_leave.group_leave_officer', raise_if_not_found=False)

        for leave in self:
            is_lwop = leave.holiday_status_id == lwop_type
            is_leave_officer = self.env.user.has_group('ahadu_hr_leave.group_leave_officer')

            # Enforce document upload for Leave Officer on LWOP requests
            if is_lwop and is_leave_officer and not leave.ceo_approved and leave.message_attachment_count == 0:
                raise UserError(_("As the Leave Officer, you must upload a supporting document before approving a Leave Without Pay request."))

        return super(HrLeave, self).action_approve()

    def action_validate(self, *args, **kwargs):
        res = super(HrLeave, self).action_validate(*args, **kwargs)

        # --- REPLENISHMENT LOGIC: Schedule the reset on use ---
        maternity_type = self.env.ref('ahadu_hr_leave.ahadu_leave_type_maternity', raise_if_not_found=False)
        paternity_type = self.env.ref('ahadu_hr_leave.ahadu_leave_type_paternity', raise_if_not_found=False)
        bereavement_type = self.env.ref('ahadu_hr_leave.ahadu_leave_type_bereavement', raise_if_not_found=False)
        
        for leave in self:
            # 1. Handle Maternity Reset (only on "first use")
            if leave.holiday_status_id == maternity_type:
                domain = [
                    ('employee_id', '=', leave.employee_id.id),
                    ('holiday_status_id', '=', maternity_type.id),
                    ('state', '=', 'validate'),
                    ('id', '!=', leave.id),
                ]
                if self.env['hr.leave'].search_count(domain) == 0:
                    _logger.info(f"First use of Maternity Leave detected for {leave.employee_id.name}. Scheduling reset.")
                    self._schedule_allocation_reset(leave, 'maternity', '_reset_maternity_allocation')

            # 2. Handle Paternity and Bereavement Resets (on EVERY use)
            elif leave.holiday_status_id in [paternity_type, bereavement_type]:
                type_name = 'paternity' if leave.holiday_status_id == paternity_type else 'bereavement'
                xml_id = 'ahadu_hr_leave.ahadu_leave_type_paternity' if leave.holiday_status_id == paternity_type else 'ahadu_hr_leave.ahadu_leave_type_bereavement'
                
                _logger.info(f"Scheduling annual replenishment for {type_name} leave for {leave.employee_id.name}.")
                self._schedule_allocation_reset(leave, type_name, f"_reset_paternity_bereavement_allocation('{xml_id}')")
        
        return res

    def _schedule_allocation_reset(self, leave, type_label, method_call):
        """ Helper to create a one-time cron for leave replenishment. """
        reset_date = leave.request_date_from + relativedelta(years=1)
        self.env['ir.cron'].create({
            'name': f"Reset {type_label.capitalize()} Leave for {leave.employee_id.name}",
            'model_id': self.env.ref('hr.model_hr_employee').id,
            'state': 'code',
            'code': f'model.browse({leave.employee_id.id}).{method_call}',
            'user_id': self.env.user.id,
            'nextcall': reset_date,
            'numbercall': 1,
        })

    @api.model_create_multi
    def create(self, vals_list):
        sick_leave_type = self.env.ref('ahadu_hr_leave.ahadu_sick_leave_request', raise_if_not_found=False)
        if not sick_leave_type:
            return super(HrLeave, self).create(vals_list)

        for vals in vals_list:
            if vals.get('holiday_status_id') == sick_leave_type.id:
                employee = self.env['hr.employee'].browse(vals.get('employee_id'))
                request_start_date = fields.Date.from_string(vals.get('date_from'))
                if not employee or not request_start_date:
                    continue
                
                # --- NEW 1-YEAR RESET LOGIC ---
                spell_start_date = employee.first_sick_leave_date_in_spell
                one_year_after_spell_start = spell_start_date + relativedelta(years=1) if spell_start_date else None

                # Start a new spell if no spell exists, or if the current request
                # is after the 1-year anniversary of the old spell's start.
                if not spell_start_date or request_start_date >= one_year_after_spell_start:
                    spell_start_date = request_start_date
                    employee.write({'first_sick_leave_date_in_spell': spell_start_date})
                
                # --- CALCULATION LOGIC (uses the determined spell_start_date) ---
                past_leaves = self.search([
                    ('employee_id', '=', employee.id),
                    ('state', '=', 'validate'),
                    ('holiday_status_id', '=', sick_leave_type.id),
                    ('date_from', '>=', spell_start_date),
                ])
                days_already_taken = sum(leave.number_of_days for leave in past_leaves)
                
                # --- SET PAY TIER INSTEAD OF CHANGING LEAVE TYPE ---
                if days_already_taken < 60:
                    vals['sick_leave_pay_tier'] = '100'
                elif days_already_taken < 120:
                    vals['sick_leave_pay_tier'] = '50'
                else:
                    vals['sick_leave_pay_tier'] = '0'

        records = super(HrLeave, self).create(vals_list)
        records._check_probation_period()
        
        return records


    def write(self, vals):
        allocations_to_update = self.env['hr.leave.allocation']
        if 'state' in vals:
            for leave in self:
                # If the leave is explicitly linked to an allocation, we target that one.
                if leave.allocation_id:
                    allocations_to_update |= leave.allocation_id
                # If not explicitly linked (fallback for older records), search for it.
                else:
                    allocations = self.env['hr.leave.allocation'].search([
                        ('employee_id', '=', leave.employee_id.id),
                        ('holiday_status_id', '=', leave.holiday_status_id.id),
                        ('state', '=', 'validate')
                    ])
                    allocations_to_update |= allocations

        # Perform the standard write operation
        res = super(HrLeave, self).write(vals)

        # Now, trigger the update on the records we identified
        if 'state' in vals and allocations_to_update:
            _logger.info(f"Leave state changed. Triggering specific allocation balance recomputation.")
            allocations_to_update._compute_leaves()
            allocations_to_update._compute_effective_remaining_leaves()
        
        return res
       
    def unlink(self):
        """
        Override unlink to trigger recomputation when a leave is deleted.
        """
        # First, find the allocations to update before the records are deleted
        allocations_to_update = self.env['hr.leave.allocation']
        for leave in self:
            allocations = self.env['hr.leave.allocation'].search([
                ('employee_id', '=', leave.employee_id.id),
                ('holiday_status_id', '=', leave.holiday_status_id.id),
                ('state', '=', 'validate')
            ])
            allocations_to_update |= allocations
        
        res = super(HrLeave, self).unlink()
        
        # Now, trigger the update
        if allocations_to_update:
            _logger.info("Leave record deleted. Triggering allocation balance recomputation.")
            allocations_to_update._compute_leaves()
            allocations_to_update._compute_effective_remaining_leaves()

        return res
    
    