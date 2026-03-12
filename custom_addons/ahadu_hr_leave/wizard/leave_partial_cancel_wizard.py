from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

class LeavePartialCancelWizard(models.TransientModel):
    _name = 'ahadu.leave.partial.cancel.wizard'
    _description = 'Leave Partial Cancel Wizard'

    # The leave_id is now populated by default_get for robustness
    leave_id = fields.Many2one('hr.leave', string="Original Leave Request", readonly=True)
    
    employee_id = fields.Many2one(related='leave_id.employee_id', readonly=True)
    # This is now a standard Date field, not a related one, to ensure it always displays.
    original_end_date = fields.Date(string="Original End Date", readonly=True)
    
    new_end_date = fields.Date(string="New End Date", required=True)
    reason = fields.Text(string="Reason for Partial Cancellation", required=True)

    @api.model
    def default_get(self, fields_list):
        """
        Pre-populates the wizard fields before it's shown to the user.
        This is the robust way to ensure the original end date is always visible.
        """
        res = super(LeavePartialCancelWizard, self).default_get(fields_list)
        if self.env.context.get('active_id'):
            leave = self.env['hr.leave'].browse(self.env.context.get('active_id'))
            res['leave_id'] = leave.id
            res['original_end_date'] = leave.request_date_to
        return res

    @api.constrains('new_end_date')
    def _check_new_end_date(self):
        for wizard in self:
            if not wizard.original_end_date:
                continue
            if wizard.new_end_date >= wizard.original_end_date:
                raise ValidationError(_("The new end date must be earlier than the original end date."))
            if wizard.new_end_date < wizard.leave_id.request_date_from:
                raise ValidationError(_("The new end date cannot be before the leave's start date."))

    def action_cancel_leave_partially(self):
        self.ensure_one()
        leave = self.leave_id
        
        original_days = leave.number_of_days
        original_description = leave.name or leave.holiday_status_id.name

        # --- THE CORRECT WORKFLOW ---
        leave.action_refuse()
        leave.action_reset_confirm()

        # Update the end date AND the description with the reason.
        # THIS IS THE FIX for the description.
        updated_description = f"{original_description} (Recalled - Reason: {self.reason})"
        leave.write({
            'request_date_to': self.new_end_date,
            'name': updated_description,
        })

        # Re-approve the leave
        leave.action_approve()
        if leave.state != 'validate':
            leave.action_validate()
        
        # Post the audit message
        new_days = leave.number_of_days
        days_refunded = original_days - new_days
        leave.message_post(
            body=_(
                "<strong>Leave Partially Canceled (Recalled)</strong><br/>"
                "The leave end date has been changed from %s to %s.<br/>"
                "Original Duration: %.2f days. New Duration: %.2f days.<br/>"
                "Days Refunded to Balance: <strong>%.2f</strong><br/>"
                "<strong>Reason:</strong> %s"
            ) % (self.original_end_date.strftime('%d %b %Y'), self.new_end_date.strftime('%d %b %Y'), original_days, new_days, days_refunded, self.reason)
        )
        
        return {'type': 'ir.actions.act_window_close'}
    
    def action_request_partial_cancellation(self):
        """
        This action is for employees. It submits the request for approval.
        """
        self.ensure_one()
        
        # Use sudo() to bypass write permissions
        self.leave_id.sudo().write({
            'new_end_date_pending': self.new_end_date,
            'partial_cancel_reason': self.reason,
            'state': 'to_cancel_partially',
        })
        self.leave_id.message_post(body=_(
            "<strong>Partial Cancellation Requested</strong><br/>"
            "New End Date Requested: %s<br/>"
            "<strong>Reason:</strong> %s"
        ) % (self.new_end_date.strftime('%d %b %Y'), self.reason))
        return {'type': 'ir.actions.act_window_close'}
        
    def action_confirm_partial_cancellation(self):
        """
        This action is for managers. It directly applies the changes.
        """
        self.ensure_one()
        
        # Security check: Only a manager can directly confirm
        if not self.env.user.has_group('hr_holidays.group_hr_holidays_manager'):
            raise UserError(_("Only a Leave Manager can directly confirm a partial cancellation."))
            
        # Call the approval method directly on the leave record
        self.leave_id.write({
            'new_end_date_pending': self.new_end_date,
            'partial_cancel_reason': self.reason,
        })
        self.leave_id.action_approve_partial_cancel()
        return {'type': 'ir.actions.act_window_close'}
    
    def action_confirm(self):
        """
        [NEW INTELLIGENT METHOD] This single method is called by the button.
        It checks the user's rights and decides which workflow to run.
        """
        self.ensure_one()
        
        # If the user is a manager, run the direct confirmation logic.
        if self.env.user.has_group('hr_holidays.group_hr_holidays_manager'):
            # Security check: Only a manager can directly confirm
            if not self.env.user.has_group('hr_holidays.group_hr_holidays_manager'):
                raise UserError(_("Only a Leave Manager can directly confirm a partial cancellation."))
                
            # Call the approval method directly on the leave record
            self.leave_id.write({
                'new_end_date_pending': self.new_end_date,
                'partial_cancel_reason': self.reason,
            })
            self.leave_id.action_approve_partial_cancel()
        
        # Otherwise, run the employee's "submit for approval" logic.
        else:
            self.leave_id.sudo().write({
                'new_end_date_pending': self.new_end_date,
                'partial_cancel_reason': self.reason,
                'state': 'to_cancel_partially',
            })
            self.leave_id.message_post(body=_(
                "<strong>Partial Cancellation Requested</strong><br/>"
                "New End Date Requested: %s<br/>"
                "<strong>Reason:</strong> %s"
            ) % (self.new_end_date.strftime('%d %b %Y'), self.reason))

        return {'type': 'ir.actions.act_window_close'}