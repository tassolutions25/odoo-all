# models/hr_activity_card_access.py

from odoo import models, fields, api


class HrActivityCardAccess(models.Model):
    _name = "hr.activity.card.access"
    _description = "Activity Card Visibility by Job Position"
    _order = "activity_type"
    _rec_name = "activity_type"

    ACTIVITY_TYPE_SELECTION = [
        ("onboarding", "Onboarding"),
        ("document_request", "Document Request"),
        ("promotion", "Promotion"),
        ("demotion", "Demotion"),
        ("transfer", "Transfer"),
        ("acting", "Acting Assignment"),
        ("temporary", "Temporary Assignment"),
        ("termination", "Termination"),
        ("resignation", "Resignation"),
        ("suspension", "Suspension"),
        ("disciplinary", "Disciplinary Actions"),
        ("guarantee", "Employee Guarantees"),
        ("retirement", "Retirement"),
        ("ctc", "CTC Adjustments"),
        ("data_change", "Data Change"),
        ("confirmation", "Confirmation"),
        ("reassign_reportees", "Reassign Reportees"),
        ("employee_reinitiate", "Employee Re-initiate"),
    ]

    activity_type = fields.Selection(
        selection=ACTIVITY_TYPE_SELECTION,
        string="Activity Card",
        required=True,
    )

    job_ids = fields.Many2many(
        "hr.job",
        "hr_activity_card_job_rel",
        "card_access_id",
        "job_id",
        string="Allowed Job Positions",
        help=(
            "Job positions that can see this activity card. "
            "Leave empty to make the card visible to all HR users."
        ),
    )

    note = fields.Char(string="Note", help="Optional description or reminder.")

    _sql_constraints = [
        (
            "unique_activity_type",
            "UNIQUE(activity_type)",
            "An access rule for this activity card already exists.",
        )
    ]

    @api.model
    def get_visible_cards_for_current_user(self):
        """
        Returns a list of activity_type strings visible to the current user
        based on their linked hr.employee's job position.

        Rules:
          - If a card has NO rule configured → hidden from everyone.
          - If a card has a rule but NO job_ids assigned → hidden from everyone.
          - If a card has a rule WITH job_ids → visible only to employees
            whose job_id is in the allowed list.
          - If the current user has no linked employee record → all cards
            are shown (safe fallback for system administrators).
        """
        # Get all configured card-access records
        all_access_records = self.search([])
        configured_types = {r.activity_type: r.job_ids.ids for r in all_access_records}

        # Get all possible activity type keys
        all_card_types = [key for key, _ in self.ACTIVITY_TYPE_SELECTION]

        # Find the employee linked to the current user
        employee = self.env["hr.employee"].search(
            [("user_id", "=", self.env.uid)], limit=1
        )

        # If no employee record found → show everything (admin fallback)
        if not employee:
            return all_card_types

        current_job_id = employee.job_id.id  # may be False/0 if not set

        visible = []
        for card_type in all_card_types:
            if card_type not in configured_types:
                # No rule configured → hidden by default
                continue
            allowed_job_ids = configured_types[card_type]
            if not allowed_job_ids:
                # Rule exists but no jobs assigned → still hidden
                continue
            if current_job_id and current_job_id in allowed_job_ids:
                # Employee's job is explicitly in the allowed list → show
                visible.append(card_type)

        return visible

