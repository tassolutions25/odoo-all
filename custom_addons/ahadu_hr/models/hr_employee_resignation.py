from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class HrEmployeeResignation(models.Model):
    _name = "hr.employee.resignation"
    _description = "Employee Resignation"
    _inherit = ["hr.approval.mixin", "mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(string="Reference", compute="_compute_name", store=True)
    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)
    resignation_date = fields.Date(
        string="Resignation Date", default=fields.Date.today, required=True
    )
    proposed_last_working_day = fields.Date(
        string="Proposed Last Working Day", required=True
    )
    reason = fields.Text(string="Reason for Resignation", required=True)

    # 30 days calculation
    archive_date = fields.Date(
        string="Scheduled Archive Date", compute="_compute_archive_date", store=True
    )

    state = fields.Selection(
        selection_add=[("withdrawn", "Withdrawn")], ondelete={"withdrawn": "cascade"}
    )
    withdrawal_date = fields.Datetime(string="Withdrawal Date", readonly=True)
    attachment_ids = fields.Many2many("ir.attachment", string="Attachments")
    activity_id = fields.Many2one("hr.employee.activity", string="Activity Record")

    @api.depends("resignation_date")
    def _compute_archive_date(self):
        for rec in self:
            if rec.resignation_date:
                rec.archive_date = rec.resignation_date + timedelta(days=30)
            else:
                rec.archive_date = False

    @api.depends("employee_id")
    def _compute_name(self):
        for rec in self:
            rec.name = (
                _("Resignation: %s") % rec.employee_id.name
                if rec.employee_id
                else _("New Resignation")
            )

    def _perform_final_approval(self):
        self.ensure_one()
        # Set the departure type so it shows up in archived list correctly
        self.employee_id.write(
            {
                "departure_type": "resignation",
                "departure_date": self.proposed_last_working_day,
            }
        )
        self.employee_id.message_post(
            body=_("Resignation approved. Scheduled to be archived on %s")
            % self.archive_date
        )

    @api.model
    def _cron_archive_resigned_employees(self):
        """Method called by the Scheduled Action"""
        _logger.info("Starting Resignation Auto-Archive Logic")

        # Use context_today to avoid UTC timezone mismatches
        today = fields.Date.context_today(self)

        # We use sudo() to ensure we find all records regardless of the cron's user rules
        records = self.sudo().search(
            [
                ("state", "=", "approved"),
                ("archive_date", "<=", today),
                ("employee_id.active", "=", True),
            ]
        )

        _logger.info("Cron found %s employees ready for archiving", len(records))

        for rec in records:
            try:
                emp = rec.employee_id
                _logger.info("System automatically archiving employee: %s", emp.name)

                # Perform the archive and set departure details
                emp.sudo().write(
                    {
                        "active": False,
                        "departure_type": "resignation",
                        "departure_date": rec.proposed_last_working_day or today,
                    }
                )

                # Optional: Post to chatter as System
                emp.message_post(
                    body=_("Notice period ended. Archived automatically by HR System.")
                )

            except Exception as e:
                _logger.error("Failed to archive resignation %s: %s", rec.id, str(e))

    def action_withdraw(self):
        for rec in self:
            if rec.state == "approved":
                raise UserError(_("Approved resignations cannot be withdrawn."))
            rec.write({"state": "withdrawn", "withdrawal_date": fields.Datetime.now()})
