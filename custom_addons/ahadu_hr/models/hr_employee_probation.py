# models/hr_employee_probation.py
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta


class HrEmployeeProbation(models.Model):
    _name = "hr.employee.probation"
    _description = "Employee Probation Review"
    _order = "probation_end_date desc"
    _inherit = ["mail.thread", "mail.activity.mixin", "hr.approval.mixin"]

    name = fields.Char(compute="_compute_name", store=True)
    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)
    probation_end_date = fields.Date(string="Probation End Date", readonly=True)
    recommendation = fields.Selection(
        [
            ("confirm", "Confirm Employment"),
            ("extend", "Extend Probation"),
            ("terminate", "Terminate Employment"),
        ],
        string="Recommendation",
        tracking=True,
    )
    extended_end_date = fields.Date(string="New Probation End Date")
    comments = fields.Text(string="Manager's Comments")
    activity_id = fields.Many2one("hr.employee.activity", string="Activity Record")

    @api.depends("employee_id", "probation_end_date")
    def _compute_name(self):
        for rec in self:
            rec.name = f"Probation Review for {rec.employee_id.name}"

    @api.onchange("employee_id")
    def _onchange_employee_id(self):
        """
        Instantly calculates and sets the probation end date in the form view
        when an employee is selected.
        """
        if self.employee_id and self.employee_id.date_of_joining:
            # Logic: 1 month for management, 2 for non-management
            months = (
                1 if self.employee_id.position_classification == "management" else 2
            )
            self.probation_end_date = self.employee_id.date_of_joining + relativedelta(
                months=months
            )
        else:
            self.probation_end_date = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("employee_id") and not vals.get("probation_end_date"):
                employee = self.env["hr.employee"].browse(vals["employee_id"])
                if employee.date_of_joining:
                    months = (
                        3 if employee.position_classification == "management" else 2
                    )
                    vals["probation_end_date"] = (
                        employee.date_of_joining + relativedelta(months=months)
                    )
        return super().create(vals_list)

    def _perform_final_approval(self):
        self.ensure_one()
        if not self.recommendation:
            raise UserError(
                _("You must select a recommendation before final approval.")
            )

        if self.recommendation == "confirm":
            self.employee_id.message_post(
                body=_(
                    "Congratulations! Your probation period has been successfully completed and your employment is confirmed."
                )
            )

        elif self.recommendation == "extend":
            if not self.extended_end_date:
                raise UserError(
                    _("Please provide a new end date for the extended probation.")
                )
            self.probation_end_date = self.extended_end_date
            self.employee_id.message_post(
                body=_(
                    f"Your probation period has been extended. The new end date is {self.extended_end_date}."
                )
            )
            # Reset the review to draft so it can go through the process again later
            self.action_draft()

        elif self.recommendation == "terminate":
            # This triggers the formal termination process
            termination_request = self.env["hr.employee.termination"].create(
                {
                    "employee_id": self.employee_id.id,
                    "termination_date": self.probation_end_date,
                    "reason": _(
                        "Termination due to unsatisfactory performance during probation period. "
                        f"Reference Probation Review: {self.name}"
                    ),
                }
            )
            self.employee_id.message_post(
                body=_(
                    "A termination process has been initiated following the probation review."
                )
            )

    @api.model
    def _cron_send_probation_reminders(self):
        """
        Scheduled action to send notifications for probation reviews ending soon.
        """
        reminder_date = fields.Date.today() + relativedelta(days=7)
        probations_due = self.search(
            [
                ("probation_end_date", "=", reminder_date),
                ("state", "in", ["draft", "submitted"]),
            ]
        )

        for review in probations_due:
            # Find recipients: the employee and the next approvers
            recipients = self.env["res.partner"]
            if review.employee_id.user_id:
                recipients |= review.employee_id.user_id.partner_id

            if review.state == "draft":
                # If draft, notify the creator (usually the manager) to submit it
                if review.create_uid.partner_id:
                    recipients |= review.create_uid.partner_id
            else:  # 'submitted'
                # If submitted, notify the next approvers
                approvers = review.next_approver_ids.mapped("user_id.partner_id")
                recipients |= approvers

            if not recipients:
                continue

            # Create a chatter notification on the probation review record
            body = _(
                "Reminder: The probation period for %(employee)s is ending on %(date)s. Please review and take the necessary action."
            ) % {
                "employee": review.employee_id.name,
                "date": review.probation_end_date,
            }
            review.message_post(
                body=body,
                partner_ids=recipients.ids,
                message_type="notification",
                subtype_xmlid="mail.mt_comment",
            )
