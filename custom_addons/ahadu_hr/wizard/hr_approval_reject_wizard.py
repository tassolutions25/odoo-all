from odoo import models, fields, api, _
from odoo.exceptions import UserError

class HrApprovalRejectWizard(models.TransientModel):
    _name = 'hr.approval.reject.wizard'
    _description = 'HR Approval Rejection Reason Wizard'

    rejection_reason = fields.Text(string="Rejection Reason", required=True)

    def action_confirm_rejection(self):
        self.ensure_one()
        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')
        if not active_model or not active_id:
            raise UserError(_("Could not find the original request to reject."))

        record = self.env[active_model].browse(active_id)
        current_user = self.env.user
        is_hr_manager = current_user.has_group("hr.group_hr_manager")
        
        if not record.can_approve and not is_hr_manager:
            raise UserError(_("You are not authorized to reject this request."))

        lines_to_update = record._get_current_approval_line()
        if not lines_to_update and is_hr_manager:
            lines_to_update = record.approval_line_ids.filtered(lambda l: l.status == 'pending')
        
        if not lines_to_update:
             raise UserError(_("Could not find a pending approval line for you on this request."))

        lines_to_update.write({
            'status': 'rejected',
            'approval_date': fields.Datetime.now(),
            'comments': self.rejection_reason
        })

        record.state = 'rejected'
        if hasattr(record, 'activity_id') and record.activity_id:
            record.activity_id.action_reject()
            
        # Post message to chatter
        record.message_post(body=_("Request rejected by %(user)s. Reason: %(reason)s") % {
            'user': current_user.name,
            'reason': self.rejection_reason
        })

        return {'type': 'ir.actions.act_window_close'}