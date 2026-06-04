# --- START OF FILE hr_employee_termination.py ---

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class HrEmployeeTermination(models.Model):
    _name = "hr.employee.termination"
    _description = "Employee Termination"
    _order = "termination_date desc"
    _inherit = ["mail.thread", "mail.activity.mixin", "hr.approval.mixin"]

    name = fields.Char(string="Reference", compute="_compute_name", store=True)
    employee_id = fields.Many2one(
        "hr.employee", string="Employee", required=True, ondelete="cascade"
    )
    termination_date = fields.Date(
        string="Termination Date", required=True, default=fields.Date.today
    )
    reason = fields.Text(string="Reason", required=True)
    attachment_ids = fields.Many2many(
        "ir.attachment",
        string="Attachments",
        help="Upload supporting documents like notices, letters, or certificates.",
    )
    activity_id = fields.Many2one(
        "hr.employee.activity",
        string="Activity Record",
        ondelete="set null",
        readonly=True,
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
        # Find the employee by their ID string
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
            self.employee_id = employee

            # Explicitly force the UI to populate the historical data/allowances instantly
            if hasattr(self, "_onchange_employee_id_fetch_history"):
                self._onchange_employee_id_fetch_history()
            if hasattr(self, "_compute_current_fields"):
                self._compute_current_fields()
            if hasattr(self, "_onchange_employee_allowances"):
                self._onchange_employee_allowances()
        else:
            self.employee_id = False

    @api.depends("employee_id")
    def _compute_name(self):
        for rec in self:
            rec.name = (
                f"Termination for {rec.employee_id.name}"
                if rec.employee_id
                else _("New Termination")
            )

    @api.model_create_multi
    def create(self, vals_list):
        terminations = super().create(vals_list)
        for termination in terminations:
            activity_vals = {
                "employee_id": termination.employee_id.id,
                "activity_type": "termination",
                "date": termination.termination_date,
                "termination_id": termination.id,
                "description": f"Termination",
                "state": "draft",
            }
            activity = self.env["hr.employee.activity"].create(activity_vals)
            termination.activity_id = activity.id
        return terminations

    def _perform_final_approval(self):
        self.ensure_one()
        if not self.employee_id.active:
            raise UserError(_("The employee is already inactive."))

        subordinates = self.employee_id.child_ids.filtered(lambda e: e.active)
        if subordinates:
            # If there are subordinates, open the wizard to reassign them.
            return {
                "name": _("Reassign Subordinates"),
                "type": "ir.actions.act_window",
                "res_model": "hr.employee.reassign.wizard",
                "view_mode": "form",
                "target": "new",
                "context": {
                    "default_termination_id": self.id,
                },
            }
        else:
            today = fields.Date.context_today(self)
            should_archive_now = self.termination_date <= today

            update_vals = {
                "departure_type": "termination",
                "departure_date": self.termination_date,
            }
            
            # Deactivate ONLY if the termination date has arrived
            if should_archive_now:
                update_vals["active"] = False

            self.employee_id.write(update_vals)
            
            if should_archive_now:
                running_contracts = self.env["hr.contract"].search(
                    [
                        ("employee_id", "=", self.employee_id.id),
                        ("state", "in", ["draft", "open"]),
                    ]
                )
                if running_contracts:
                    running_contracts.write(
                        {"date_end": self.termination_date, "state": "close"}
                    )

            if self.activity_id:
                self.activity_id.action_approve()

            if not should_archive_now:
                self.employee_id.message_post(
                    body=_("Termination approved. The employee will be archived automatically on %s.") % self.termination_date
                )

    @api.model
    def _cron_archive_terminated_employees(self):
        """Method called by the Scheduled Action"""
        _logger.info("Starting Termination Auto-Archive Logic")

        today = fields.Date.context_today(self)

        records = self.sudo().search(
            [
                ("state", "=", "approved"),
                ("termination_date", "<=", today),
                ("employee_id.active", "=", True),
            ]
        )

        _logger.info("Cron found %s employees ready for termination archiving", len(records))

        for rec in records:
            try:
                emp = rec.employee_id
                _logger.info("System automatically archiving terminated employee: %s", emp.name)

                emp.sudo().write(
                    {
                        "active": False,
                        "departure_type": "termination",
                        "departure_date": rec.termination_date,
                    }
                )

                # Close contracts
                running_contracts = self.env["hr.contract"].search(
                    [
                        ("employee_id", "=", emp.id),
                        ("state", "in", ["draft", "open"]),
                    ]
                )
                if running_contracts:
                    running_contracts.write(
                        {"date_end": rec.termination_date, "state": "close"}
                    )

                emp.message_post(
                    body=_("Termination date reached. Archived automatically by HR System.")
                )

            except Exception as e:
                _logger.error("Failed to archive termination %s: %s", rec.id, str(e))