from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HrEmployeeActivity(models.Model):
    _inherit = "hr.employee.activity"

    activity_type = fields.Selection(
        selection_add=[
            ("onboarding", "Onboarding"),
            ("document_request", "Document Request"),
        ],
        ondelete={"onboarding": "cascade", "document_request": "cascade"},
    )
    onboarding_id = fields.Many2one(
        "hr.employee.onboarding", string="Onboarding Record", ondelete="set null"
    )
    document_request_id = fields.Many2one(
        "hr.document.request", string="Document Request Record", ondelete="set null"
    )

    def action_open_related_record(self):
        self.ensure_one()
        if self.activity_type == "onboarding":
            related_record = self.onboarding_id
        elif self.activity_type == "document_request":
            related_record = self.document_request_id
        else:
            # For all other types, call the original method from the parent module (ahadu_hr)
            return super().action_open_related_record()

        # Common logic for this module's activity types
        if not related_record.exists():
            raise UserError(
                _(
                    "The original document for this activity could not be found. "
                    "It may have been deleted."
                )
            )
        return {
            "type": "ir.actions.act_window",
            "res_model": related_record._name,
            "res_id": related_record.id,
            "view_mode": "form",
            "target": "current",
        }
