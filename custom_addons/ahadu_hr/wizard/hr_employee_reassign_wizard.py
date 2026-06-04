# --- START OF FILE wizard/hr_employee_reassign_wizard.py ---

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HrEmployeeReassignWizard(models.TransientModel):
    _name = "hr.employee.reassign.wizard"
    _description = "Reassign Subordinates Wizard"

    departing_manager_id = fields.Many2one(
        "hr.employee", string="Departing Manager", readonly=True
    )
    subordinate_ids = fields.Many2many(
        "hr.employee", string="Subordinates to Reassign", readonly=True
    )
    new_manager_id = fields.Many2one(
        "hr.employee",
        string="New Manager",
        required=True,
        domain="[('id', '!=', departing_manager_id)]",
    )
    termination_id = fields.Many2one(
        "hr.employee.termination", string="Termination Record", readonly=True
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get("active_id")
        if active_id:
            termination = self.env["hr.employee.termination"].browse(active_id)
            departing_manager = termination.employee_id
            res.update(
                {
                    "termination_id": termination.id,
                    "departing_manager_id": departing_manager.id,
                    "subordinate_ids": [(6, 0, departing_manager.child_ids.ids)],
                }
            )
        return res

    def action_reassign_and_terminate(self):
        self.ensure_one()
        if not self.subordinate_ids:
            raise ValidationError(_("There are no subordinates to reassign."))

        # Reassign subordinates
        self.subordinate_ids.write({"parent_id": self.new_manager_id.id})

        for emp in self.subordinate_ids:
            emp.message_post(
                body=_(
                    "Your manager has been changed from %(old_manager)s to %(new_manager)s due to a departure."
                )
                % {
                    "old_manager": self.departing_manager_id.name,
                    "new_manager": self.new_manager_id.name,
                }
            )

        termination = self.termination_id
        today = fields.Date.context_today(self)
        should_archive_now = termination.termination_date <= today

        update_vals = {
            "departure_type": "termination",
            "departure_date": termination.termination_date,
        }

        if should_archive_now:
            update_vals["active"] = False

        # Apply updates
        termination.employee_id.write(update_vals)

        # End the active contract only if it's archiving now
        if should_archive_now:
            running_contracts = self.env["hr.contract"].search(
                [
                    ("employee_id", "=", termination.employee_id.id),
                    ("state", "in", ["draft", "open"]),
                ]
            )
            if running_contracts:
                running_contracts.write(
                    {"date_end": termination.termination_date, "state": "close"}
                )

        if termination.activity_id:
            termination.activity_id.action_approve()

        msg = _(
            "%(count)d subordinates were successfully reassigned to %(new_manager)s."
        ) % {
            "count": len(self.subordinate_ids),
            "new_manager": self.new_manager_id.name,
        }

        if should_archive_now:
            msg += _(
                " The termination process is now complete and the employee has been archived."
            )
        else:
            msg += (
                _(" The employee will be archived automatically on %s.")
                % termination.termination_date
            )

        termination.message_post(body=msg)

        return {"type": "ir.actions.act_window_close"}
