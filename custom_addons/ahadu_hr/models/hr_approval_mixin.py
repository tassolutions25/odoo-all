from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval
import logging

_logger = logging.getLogger(__name__)


class HrApprovalMixin(models.AbstractModel):
    _name = "hr.approval.mixin"
    _description = "HR Multi-level Approval Mixin"

    state = fields.Selection([
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        copy=False,
        readonly=True,
    )

    approval_line_ids = fields.One2many(
        "hr.approval.line",
        "res_id",
        string="Approval Chain",
        domain=lambda self: [("res_model", "=", self._name)],
        copy=False,
        readonly=True,
    )

    next_approver_ids = fields.Many2many(
        "hr.employee",
        string="Next Approver(s)",
        compute="_compute_next_approvers",
    )
    can_approve = fields.Boolean(
        string="Can Approve",
        compute="_compute_can_approve",
    )

    def _get_employee_for_approval(self):
        """Returns the employee record for whom the request is being made."""
        if hasattr(self, "employee_id"):
            return self.employee_id
        raise NotImplementedError(
            "The model inheriting hr.approval.mixin must have an 'employee_id' field or override _get_employee_for_approval."
        )

    def _perform_final_approval(self):
        """Contains the specific logic to execute upon final approval."""
        raise NotImplementedError()

    def _send_approval_notification(self, approvers):
        """Sends Odoo notification to a set of approvers."""
        self.ensure_one()
        if not approvers:
            return

        if not hasattr(self, "message_post"):
            _logger.warning(
                f"Model {self._name} does not inherit mail.thread, cannot send notifications."
            )
            return

        partners = approvers.mapped("user_id.partner_id").filtered(lambda p: p.active)
        if not partners:
            _logger.warning(
                f"No active partners with linked users found for approvers on {self._name} ID {self.id}"
            )
            return

        record_name = self.display_name or self._description
        body = _(
            "Your approval is requested for the following document: "
            "<a href='#' data-oe-model='%(model)s' data-oe-id='%(res_id)d'>%(name)s</a>"
        ) % {
            "model": self._name,
            "res_id": self.id,
            "name": record_name,
        }

        self.message_post(
            body=body,
            partner_ids=partners.ids,
            message_type="notification",
            subtype_xmlid="mail.mt_note",
        )
        _logger.info(
            f"Sent approval notification for '{record_name}' to partners: {partners.ids}"
        )

    @api.depends("approval_line_ids.status")
    def _compute_next_approvers(self):
        for rec in self:
            pending_lines = rec.approval_line_ids.filtered(
                lambda l: l.status == "pending"
            )
            if pending_lines:
                min_sequence = min(pending_lines.mapped("sequence"))
                rec.next_approver_ids = pending_lines.filtered(
                    lambda l: l.sequence == min_sequence
                ).mapped("approver_id")
            else:
                rec.next_approver_ids = self.env["hr.employee"]

    def _compute_can_approve(self):
        for rec in self:
            current_user = self.env.user
            if not current_user.employee_id:
                rec.can_approve = False
                continue
            rec.can_approve = current_user.employee_id in rec.next_approver_ids

    def _find_applicable_policy(self):
        """Finds the first matching approval policy for this record."""
        self.ensure_one()
        policies = self.env["hr.approval.policy"].search([("model_id.model", "=", self._name), ("active", "=", True)],
            order="sequence",
        )
        for policy in policies:
            try:
                domain = safe_eval(policy.domain, {"record": self})
                if self.search_count(domain + [("id", "=", self.id)]):
                    return policy

                if self.filtered_domain(domain):
                    return policy
            except Exception as e:
                _logger.error(f"Error evaluating domain for policy {policy.name}: {e}")
                continue
        return None

    def _generate_approval_chain(self):
        self.ensure_one()
        self.approval_line_ids.unlink()

        policy = self._find_applicable_policy()
        if not policy:
            raise UserError(
                _(
                    "No applicable approval policy found for this request. Please contact the HR department."
                )
            )

        vals_list =[]
        employee = self._get_employee_for_approval()
        last_sequence = 0

        for line in policy.line_ids.sorted("sequence"):
            approvers_to_add = self.env["hr.employee"]

            if line.approver_type == "managerial_chain":
                current_approver = employee.parent_id
                visited = set()
                chain_sequence = line.sequence
                while current_approver and current_approver.id not in visited:
                    vals_list.append(
                        {
                            "approver_id": current_approver.id,
                            "sequence": chain_sequence,
                            "res_model": self._name,
                            "res_id": self.id,
                        }
                    )
                    visited.add(current_approver.id)
                    current_approver = current_approver.parent_id
                    chain_sequence += 1
                last_sequence = chain_sequence - 1
                continue  # Move to the next policy line

            elif line.approver_type == "job_position":
                if line.job_id:
                    approvers_to_add = self.env["hr.employee"].search([("job_id", "=", line.job_id.id), ("active", "=", True)]
                    )

            if not approvers_to_add and line.is_required:
                raise UserError(
                    _(
                        "No active employee found for the required approval step: '%s'.",
                        line.job_id.name or "N/A",
                    )
                )

            current_line_sequence = max(line.sequence, last_sequence + 1)
            for approver in approvers_to_add:
                vals_list.append(
                    {
                        "approver_id": approver.id,
                        "sequence": current_line_sequence,
                        "res_model": self._name,
                        "res_id": self.id,
                    }
                )

        if not vals_list:
            # No approvers found, auto-approve
            _logger.info(
                f"No approvers found for policy {policy.name}, auto-approving."
            )
            self.state = "approved"
            self._perform_final_approval()
            return

        # Deduplicate while preserving order
        final_vals =[]
        seen = set()
        for d in vals_list:
            key = (d["approver_id"], d["sequence"])
            if key not in seen:
                seen.add(key)
                final_vals.append(d)

        if final_vals:
            self.env["hr.approval.line"].create(final_vals)

    def action_submit(self):
        for rec in self:
            rec._generate_approval_chain()
            if rec.state != "approved":
                rec.state = "submitted"
            if hasattr(rec, "activity_id") and rec.activity_id:
                rec.activity_id.action_submit()
            rec._send_approval_notification(rec.next_approver_ids)

    def _get_current_approval_line(self):
        self.ensure_one()
        current_user = self.env.user
        if not current_user.employee_id:
            return self.env["hr.approval.line"]

        return self.approval_line_ids.filtered(
            lambda line: line.approver_id == current_user.employee_id
            and line.approver_id in self.next_approver_ids
            and line.status == "pending"
        )

    def action_approve_step(self):
        if not self.can_approve:
            raise UserError(_("You are not authorized to approve this request."))

        for rec in self:
            lines_to_update = rec._get_current_approval_line()
            if not lines_to_update:
                raise UserError(
                    _("Could not find a pending approval line for you on this request.")
                )

            # Find peers who share the same job position and sequence 
            # to remove them so it acts as an "OR" condition pool
            peers_to_remove = self.env["hr.approval.line"]
            for line in lines_to_update:
                job_id = line.approver_id.job_id
                if job_id:
                    peers = rec.approval_line_ids.filtered(
                        lambda l: l.status == "pending"
                        and l.sequence == line.sequence
                        and l.approver_id.job_id == job_id
                        and l.id != line.id
                    )
                    peers_to_remove |= peers

            lines_to_update.write(
                {"status": "approved", "approval_date": fields.Datetime.now()}
            )
            
            # Delete parallel approvers in the same sequence and job position
            if peers_to_remove:
                peers_to_remove.unlink()

            # Re-fetch next approvers after the update
            pending_lines_after = rec.approval_line_ids.filtered(
                lambda l: l.status == "pending"
            )

            if not pending_lines_after:
                rec.state = "approved"
                rec._perform_final_approval()
                if hasattr(rec, "activity_id") and rec.activity_id:
                    rec.activity_id.action_approve()
            else:
                # Need to re-compute to get the *new* next approvers
                rec._compute_next_approvers()
                rec._send_approval_notification(rec.next_approver_ids)

    def action_reject(self):
        # Allow rejection without being the current approver if you are an HR manager
        is_hr_manager = self.env.user.has_group("hr.group_hr_manager")
        if not self.can_approve and not is_hr_manager:
            raise UserError(_("You are not authorized to reject this request."))

        return {
            "name": _("Rejection Reason"),
            "type": "ir.actions.act_window",
            "res_model": "hr.approval.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "active_model": self._name,
                "active_id": self.id,
            },
        }

    def action_draft(self):
        """
        Resets the approval request back to the 'draft' state.
        This action clears the existing approval chain.
        """
        for rec in self:
            # Set the main record's state back to draft
            rec.write({"state": "draft"})

            # Delete the previous approval lines, as they are no longer relevant
            rec.approval_line_ids.unlink()

            # If the record is linked to an activity, reset that activity to draft as well
            if hasattr(rec, "activity_id") and rec.activity_id:
                if hasattr(rec.activity_id, "action_draft"):
                    rec.activity_id.action_draft()