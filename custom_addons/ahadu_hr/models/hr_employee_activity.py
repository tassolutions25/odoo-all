from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HrEmployeeActivity(models.Model):
    _name = "hr.employee.activity"
    _description = "Employee Activity"
    _order = "create_date desc"
    _rec_name = "activity_type"

    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)
    activity_type = fields.Selection(
        [
            ("promotion", "Promotion"),
            ("demotion", "Demotion"),
            ("transfer", "Transfer"),
            ("disciplinary", "Disciplinary Action"),
            ("guarantee", "Guarantee"),
            ("termination", "Termination"),
            ("acting", "Acting Assignment"),
            ("temporary", "Temporary Assignment"),
            ("ctc", "CTC Adjustment"),
            ("retirement", "Retirement"),
            ("data_change", "Data Change"),
            ("confirmation", "Confirmation"),
            ("reassign_reportees", "Reassign Reportees"),
            ("employee_reinitiate", "Employee Reinitiate"),
        ],
        string="Activity Type",
        required=True,
    )

    date = fields.Date(string="Activity Date", default=fields.Date.today)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        string="State",
        default="draft",
    )

    description = fields.Text(string="Description")
    attachment_ids = fields.Many2many("ir.attachment", string="Attachments")

    # Reference fields for specific activity records
    promotion_id = fields.Many2one(
        "hr.employee.promotion", string="Promotion Record", ondelete="set null"
    )
    transfer_id = fields.Many2one(
        "hr.employee.transfer", string="Transfer Record", ondelete="set null"
    )
    demotion_id = fields.Many2one(
        "hr.employee.demotion", string="Demotion Record", ondelete="set null"
    )
    disciplinary_id = fields.Many2one(
        "hr.employee.disciplinary", string="Disciplinary Record", ondelete="set null"
    )
    guarantee_id = fields.Many2one(
        "hr.employee.guarantee", string="Guarantee Record", ondelete="set null"
    )
    retirement_id = fields.Many2one(
        "hr.employee.retirement", string="Retirement Record", ondelete="set null"
    )
    termination_id = fields.Many2one(
        "hr.employee.termination", string="Termination Record", ondelete="set null"
    )
    acting_id = fields.Many2one(
        "hr.employee.acting", string="Acting Record", ondelete="set null"
    )
    temporary_assignment_id = fields.Many2one(
        "hr.employee.temporary.assignment",
        string="Temporary Assignment Record",
        ondelete="set null",
    )
    ctc_id = fields.Many2one(
        "hr.employee.ctc", string="CTC Record", ondelete="set null"
    )
    data_change_id = fields.Many2one(
        "hr.employee.data.change", string="Data Change Record", ondelete="set null"
    )
    confirmation_id = fields.Many2one(
        "hr.employee.confirmation", string="Confirmation Record", ondelete="set null"
    )
    reassign_id = fields.Many2one(
        "hr.employee.reassign", string="Reassign Record", ondelete="set null"
    )
    reinitiate_id = fields.Many2one(
        "hr.employee.reinitiate", string="Reinitiate Record", ondelete="set null"
    )

    def action_open_related_record(self):
        self.ensure_one()
        mapping = {
            "promotion": "promotion_id",
            "demotion": "demotion_id",
            "transfer": "transfer_id",
            "disciplinary": "disciplinary_id",
            "guarantee": "guarantee_id",
            "termination": "termination_id",
            "acting": "acting_id",
            "temporary": "temporary_assignment_id",
            "retirement": "retirement_id",
            "ctc": "ctc_id",
            "data_change": "data_change_id",
            "confirmation": "confirmation_id",
            "reassign_reportees": "reassign_id",
            "employee_reinitiate": "reinitiate_id",
        }
        field_name = mapping.get(self.activity_type)
        if not field_name:
            return {}

        related_record = self[field_name]
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

    def action_submit(self):
        self.state = "submitted"

    def action_approve(self):
        self.state = "approved"

    def action_reject(self):
        self.state = "rejected"

    def action_reset_to_draft(self):
        self.state = "draft"
