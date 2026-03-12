# ahadu_hr/models/hr_employee_acting.py

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HrEmployeeActing(models.Model):
    _name = "hr.employee.acting"
    _description = "Employee Acting Assignment"
    _order = "start_date desc"
    _inherit = ["hr.approval.mixin", "mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Reference", compute="_compute_name", store=True)
    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)
    acting_job_id = fields.Many2one("hr.job", string="Acting Position", required=True)
    start_date = fields.Date(
        string="Start Date", required=True, default=fields.Date.today
    )
    end_date = fields.Date(string="End Date")
    allowance_amount = fields.Monetary(
        string="Acting Allowance", help="Additional allowance for this period."
    )
    currency_id = fields.Many2one("res.currency", related="employee_id.currency_id")
    reason = fields.Text(string="Reason", required=True)
    activity_id = fields.Many2one(
        "hr.employee.activity", string="Activity Record", ondelete="set null"
    )

    # Extend state selection for this model
    state = fields.Selection(
        selection_add=[("completed", "Completed")], ondelete={"completed": "cascade"}
    )
    current_department_id = fields.Many2one(
        "hr.department",
        string="Current Department",
        compute="_compute_current_fields",
        readonly=True,
    )
    current_branch_id = fields.Many2one(
        "hr.branch",
        string="Current Branch",
        compute="_compute_current_fields",
        readonly=True,
    )

    # New assignment details
    new_department_id = fields.Many2one(
        "hr.department", string="New Department", tracking=True
    )
    new_branch_id = fields.Many2one("hr.branch", string="New Branch", tracking=True)

    # Original details (stored on approval)
    original_department_id = fields.Many2one(
        "hr.department", string="Original Department", readonly=True
    )
    original_branch_id = fields.Many2one(
        "hr.branch", string="Original Branch", readonly=True
    )

    @api.depends("employee_id", "acting_job_id")
    def _compute_name(self):
        for rec in self:
            if rec.employee_id and rec.acting_job_id:
                rec.name = f"Acting Assignment for {rec.employee_id.name} as {rec.acting_job_id.name}"
            else:
                rec.name = _("New Acting Assignment")

    # @api.constrains("start_date", "end_date")
    # def _check_dates(self):
    #     for record in self:
    #         if record.start_date > record.end_date:
    #             raise ValidationError(_("The start date cannot be after the end date."))

    @api.depends("employee_id")
    def _compute_current_fields(self):
        for rec in self:
            if rec.employee_id:
                employee = rec.employee_id
                rec.current_department_id = employee.department_id
                rec.current_branch_id = employee.branch_id
            else:
                rec.current_department_id = False
                rec.current_branch_id = False

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            activity = self.env["hr.employee.activity"].create(
                {
                    "employee_id": rec.employee_id.id,
                    "activity_type": "acting", 
                    "date": rec.start_date,
                    "acting_id": rec.id,
                    "description": f"Acting assignment for position: {rec.acting_job_id.name}",
                }
            )
            rec.activity_id = activity.id
        return records

    def _perform_final_approval(self):
        self.ensure_one()
        employee = self.employee_id

        # Store original data before making changes
        self.write(
            {
                "original_department_id": employee.department_id.id,
                "original_branch_id": employee.branch_id.id,
            }
        )

        update_vals = {"is_acting": True, "acting_job_id": self.acting_job_id.id}
        if self.new_department_id:
            update_vals["department_id"] = self.new_department_id.id
        if self.new_branch_id:
            update_vals["branch_id"] = self.new_branch_id.id

        employee.write(update_vals)

        message_body = _(
            f"Your acting assignment for the position '{self.acting_job_id.name}' starting from {self.start_date} has been approved."
        )
        if self.new_department_id or self.new_branch_id:
            message_body += _(
                "\nYour department/branch has been temporarily updated for the duration of this assignment."
            )

        self.employee_id.message_post(body=message_body)

    # def _end_acting_assignment(self):
    #     for assignment in self:
    #         assignment.employee_id.write({"is_acting": False, "acting_job_id": False})
    #         assignment.state = "completed"
    #         assignment.employee_id.message_post(
    #             body=_(
    #                 f"Your acting assignment for '{assignment.acting_job_id.name}' has ended."
    #             )
    #         )

    # @api.model
    # def _check_end_acting_assignments(self):
    #     """Cron job to automatically end acting assignments."""
    #     today = fields.Date.today()
    #     assignments_to_end = self.search(
    #         [("state", "=", "approved"), ("end_date", "<", today)]
    #     )
    #     assignments_to_end._end_acting_assignment()

    def action_revoke(self):
        """Revokes the acting assignment and reverts employee details."""
        self.ensure_one()
        if self.state != "approved":
            raise ValidationError(_("Only approved acting assignments can be revoked."))

        employee = self.employee_id

        # Prepare values to revert from stored original data
        revert_vals = {
            "department_id": self.original_department_id.id,
            "branch_id": self.original_branch_id.id,
            "is_acting": False,
            "acting_job_id": False,
        }

        employee.write(revert_vals)
        self.state = "completed"

        self.employee_id.message_post(
            body=_(
                f"Your acting assignment for '{self.acting_job_id.name}' has been revoked. Your details have been reverted to their original state."
            )
        )
