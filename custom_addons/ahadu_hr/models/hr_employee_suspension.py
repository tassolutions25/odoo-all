from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HrEmployeeSuspension(models.Model):
    _name = "hr.employee.suspension"
    _description = "Employee Suspension"
    # Inherit approval mixin for the workflow
    _inherit = ["hr.approval.mixin", "mail.thread", "mail.activity.mixin"]
    _order = "start_date desc"

    name = fields.Char(string="Reference", compute="_compute_name", store=True)
    employee_id = fields.Many2one(
        "hr.employee", string="Employee", required=True, ondelete="cascade"
    )
    employee_number_search = fields.Char(
        string="Employee ID",
        compute="_compute_employee_number_search",
        inverse="_inverse_employee_number_search",
        store=True,
        readonly=False,
    )

    @api.depends("employee_id")
    def _compute_employee_number_search(self):
        for rec in self:
            if rec.employee_id:
                rec.employee_number_search = rec.employee_id.employee_id

    def _inverse_employee_number_search(self):
        for rec in self:
            if rec.employee_number_search:
                rec._sync_employee_data()

    @api.onchange("employee_number_search")
    def _onchange_employee_number_search(self):
        if self.employee_number_search:
            self._sync_employee_data()

    def _sync_employee_data(self):
        employee = (
            self.env["hr.employee"]
            .sudo()
            .with_context(active_test=False)
            .search(
                [("employee_id", "=ilike", self.employee_number_search.strip())],
                limit=1,
            )
        )
        if employee:
            self.employee_id = employee.id

    reason = fields.Text(string="Reason for Suspension", required=True)
    start_date = fields.Date(
        string="Suspension Start Date", default=fields.Date.today, required=True
    )

    duration_type = fields.Selection(
        [("fixed", "Fixed Duration"), ("open", "Open-Ended")],
        string="Duration Type",
        default="fixed",
        required=True,
    )

    end_date = fields.Date(string="Suspension End Date")

    activity_id = fields.Many2one(
        "hr.employee.activity", string="Activity Record", readonly=True
    )

    @api.depends("employee_id", "start_date")
    def _compute_name(self):
        for rec in self:
            rec.name = (
                f"SUSP/{rec.employee_id.name}/{rec.start_date}"
                if rec.employee_id
                else "New Suspension"
            )

    def _get_employee_for_approval(self):
        return self.employee_id

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            activity = self.env["hr.employee.activity"].create(
                {
                    "employee_id": rec.employee_id.id,
                    "activity_type": "disciplinary",  # Categorize as disciplinary
                    "date": rec.start_date,
                    "suspension_id": rec.id,  # We will add this field in next step
                    "description": _("Suspension Request: %s") % rec.reason[:50],
                    "state": "draft",
                }
            )
            rec.activity_id = activity.id
        return records

    def action_submit(self):
        res = super().action_submit()
        if self.activity_id:
            self.activity_id.write({"state": "submitted"})
        return res

    def _perform_final_approval(self):
        """This runs when the approval workflow is finished."""
        self.ensure_one()
        if self.employee_id.ahadu_state == "suspended":
            raise UserError(_("This employee is already suspended."))

        # Change status and restrict access
        self.employee_id.sudo().write({"ahadu_state": "suspended"})
        self.employee_id.message_post(
            body=_("Suspension request approved. Employee is now Suspended.")
        )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("reinstated", "Reinstated"),
            ("rejected", "Rejected"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )

    employee_status = fields.Selection(
        related="employee_id.ahadu_state",
        string="Current Employee Status",
        store=False,
    )

    def action_reinstate(self):
        """Manual Unsuspend Logic"""
        for rec in self:
            if rec.employee_id.ahadu_state != "suspended":
                raise UserError(_("This employee is already Active."))

            rec.employee_id.sudo().write({"ahadu_state": "active"})

            rec.write({"state": "reinstated"})

            rec.employee_id.message_post(
                body=_("Employee has been manually REINSTATED. System access restored.")
            )
            rec.message_post(body=_("Suspension retracted manually by HR."))

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Employee Reinstated"),
                    "message": _(
                        "Employee %s is now Active. System access has been restored."
                    )
                    % rec.employee_id.name,
                    "sticky": False,  # This makes it a toast (disappears after a few seconds)
                    "type": "success",  # Green background
                    "next": {
                        "type": "ir.actions.act_window_close"
                    },  # Optional: Closes the record or refreshes
                },
            }

    def action_draft(self):
        """Allow resetting to draft to 'cancel' or 'retract' fully."""
        res = super().action_draft()
        for rec in self:
            if rec.employee_id.ahadu_state == "suspended":
                rec.employee_id.sudo().write({"ahadu_state": "active"})
        return res
