from odoo import models, fields, api, _

class LeaveFullCancelWizard(models.TransientModel):
    _name = 'ahadu.leave.full.cancel.wizard'
    _description = 'Full Leave Cancellation Wizard'

    # The original leave request we are cancelling
    leave_id = fields.Many2one('hr.leave', string="Leave to Cancel", readonly=True,
        default=lambda self: self.env.context.get('active_id'))
    
    # The reason for the cancellation
    reason = fields.Text(string="Reason for Cancellation", required=True)

    def action_submit_cancellation_request(self):
        """
        This method is called by the wizard button. It writes the reason to the
        leave record and moves it to the 'to_cancel' state for approval.
        """
        self.ensure_one()
        
        # Use sudo() to bypass the standard user's write permission error
        self.leave_id.sudo().write({
            'full_cancel_reason': self.reason,
            'state': 'to_cancel',
        })
        
        # Post a message to the chatter to notify the manager
        self.leave_id.message_post(body=_(
            "<strong>Full Cancellation Requested</strong><br/>"
            "<strong>Reason:</strong> %s"
        ) % (self.reason))
        
        return {'type': 'ir.actions.act_window_close'}