from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HrApprovalRejectWizard(models.TransientModel):
    _name = "hr.approval.reject.wizard"
    _description = "HR Approval Rejection Reason Wizard"

    rejection_reason = fields.Text(string="Rejection Reason", required=True)

    def action_confirm_rejection(self):
        self.ensure_one()
        active_model = self.env.context.get("active_model")
        active_ids = self.env.context.get("active_ids")

        if not active_model or not active_ids:
            # Fallback to active_id if active_ids is somehow missing
            active_id = self.env.context.get("active_id")
            if active_id:
                active_ids = [active_id]
            else:
                raise UserError(_("Could not find the original request(s) to reject."))

        records = self.env[active_model].browse(active_ids)
        current_user = self.env.user
        is_hr_manager = current_user.has_group("hr.group_hr_manager")

        for record in records:
            if not record.can_approve and not is_hr_manager:
                raise UserError(
                    _("You are not authorized to reject the request for %s.")
                    % (record.display_name or record.id)
                )

            lines_to_update = record._get_current_approval_line()
            if not lines_to_update and is_hr_manager:
                lines_to_update = record.approval_line_ids.filtered(
                    lambda l: l.status == "pending"
                )

            if not lines_to_update:
                raise UserError(
                    _(
                        "Could not find a pending approval line for you on the request for %s."
                    )
                    % (record.display_name or record.id)
                )

            lines_to_update.write(
                {
                    "status": "rejected",
                    "approval_date": fields.Datetime.now(),
                    "comments": self.rejection_reason,
                }
            )

            record.state = "rejected"
            record.invalidate_recordset(fnames=["approval_line_ids", "next_approver_ids"])
            if hasattr(record, "activity_id") and record.activity_id:
                record.activity_id.action_reject()

            # Post message to chatter
            record.message_post(
                body=_("Request rejected by %(user)s. Reason: %(reason)s")
                % {"user": current_user.name, "reason": self.rejection_reason}
            )

        return {"type": "ir.actions.act_window_close"}
