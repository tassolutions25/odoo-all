from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HrEmployeeTemporaryAssignment(models.Model):
    _name = "hr.employee.temporary.assignment"
    _description = "Employee Temporary Assignment"
    _inherit = ["mail.thread", "mail.activity.mixin", "hr.approval.mixin"]
    _order = "create_date desc"

    name = fields.Char(string="Reference", compute="_compute_name", store=True)
    employee_id = fields.Many2one(
        "hr.employee",
        string="Employee",
        required=True,
        tracking=True,
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
        else:
            self.employee_id = False

    start_date = fields.Date(string="Start Date", required=True, tracking=True)
    end_date = fields.Date(string="End Date", required=True, tracking=True)

    # current_job_id = fields.Many2one(
    #     "hr.job",
    #     string="Current Job",
    #     compute="_compute_current_fields",
    #     readonly=True,
    # )
    current_department_id = fields.Many2one(
        "hr.department",
        string="Current Department",
        compute="_compute_current_fields",
        readonly=True,
    )
    current_parent_id = fields.Many2one(
        "hr.employee",
        string="Current Manager",
        compute="_compute_current_fields",
        readonly=True,
    )
    current_branch_id = fields.Many2one(
        "hr.branch",
        string="Current Branch",
        compute="_compute_current_fields",
        readonly=True,
    )
    current_division_id = fields.Many2one(
        "hr.division",
        string="Current Division",
        compute="_compute_current_fields",
        readonly=True,
    )
    current_cost_center_id = fields.Many2one(
        "hr.cost.center",
        string="Current Cost Center",
        compute="_compute_current_fields",
        readonly=True,
    )

    # New Assignment Details
    # new_job_id = fields.Many2one("hr.job", string="New Job Position", tracking=True)
    new_department_id = fields.Many2one(
        "hr.department", string="New Department", tracking=True
    )
    new_parent_id = fields.Many2one("hr.employee", string="New Manager", tracking=True)
    new_branch_id = fields.Many2one("hr.branch", string="New Branch", tracking=True)
    new_division_id = fields.Many2one(
        "hr.division",
        string="New Division",
        tracking=True,
    )
    new_cost_center_id = fields.Many2one(
        "hr.cost.center", string="New Cost Center", tracking=True
    )

    # Original Details (stored on approval)
    # original_job_id = fields.Many2one(
    #     "hr.job", string="Original Job Position", readonly=True
    # )
    original_department_id = fields.Many2one(
        "hr.department", string="Original Department", readonly=True
    )
    original_parent_id = fields.Many2one(
        "hr.employee", string="Original Manager", readonly=True
    )
    original_branch_id = fields.Many2one(
        "hr.branch", string="Original Branch", readonly=True
    )
    original_division_id = fields.Many2one(
        "hr.division", string="Original Division", readonly=True
    )
    original_cost_center_id = fields.Many2one(
        "hr.cost.center", string="Original Cost Center", readonly=True
    )

    notes = fields.Text(string="Notes")
    activity_id = fields.Many2one(
        "hr.employee.activity", string="Related Activity", ondelete="cascade"
    )

    state = fields.Selection(
        selection_add=[("completed", "Completed"), ("cancelled", "Cancelled")],
        ondelete={"completed": "cascade", "cancelled": "cascade"},
    )
    attachment_ids = fields.Many2many(
        "ir.attachment",
        string="Attachments",
        help="Upload supporting documents like notices, letters, or certificates.",
    )

    @api.depends("employee_id")
    def _compute_name(self):
        for rec in self:
            rec.name = (
                f"Temporary Assignment for {rec.employee_id.name}"
                if rec.employee_id
                else _("New Temporary Assignment")
            )

    # --- dynamically update the domain ---
    @api.onchange("new_department_id")
    def _onchange_new_department_id(self):
        # Reset the division when the department changes
        # self.new_division_id = False
        if self.new_department_id:
            # Return a domain to filter divisions based on the selected department
            return {
                "domain": {
                    "new_division_id": [
                        ("department_id", "=", self.new_department_id.id)
                    ]
                }
            }
        else:
            # If no department is selected, the domain should not allow any selection.
            # A domain of [('id', '=', False)] ensures the list is always empty.
            return {"domain": {"new_division_id": [("id", "=", False)]}}

    @api.depends("employee_id")
    def _compute_current_fields(self):
        for rec in self:
            if rec.employee_id:
                employee = rec.employee_id
                # rec.current_job_id = employee.job_id
                rec.current_department_id = employee.department_id
                rec.current_parent_id = employee.parent_id
                rec.current_branch_id = employee.branch_id
                rec.current_division_id = employee.division_id
                rec.current_cost_center_id = employee.cost_center_id
            else:
                # rec.current_job_id = False
                rec.current_department_id = False
                rec.current_parent_id = False
                rec.current_branch_id = False
                rec.current_division_id = False
                rec.current_cost_center_id = False

    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        for record in self:
            if (
                record.start_date
                and record.end_date
                and record.start_date > record.end_date
            ):
                raise ValidationError(
                    _("The start date cannot be later than the end date.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            activity = self.env["hr.employee.activity"].create(
                {
                    "employee_id": rec.employee_id.id,
                    "activity_type": "temporary",
                    "date": rec.start_date,
                    "description": f"Temporary assignment to {rec.employee_id.name if rec.employee_id else 'Temporary Acting'}",
                    "temporary_assignment_id": rec.id,
                }
            )
            rec.activity_id = activity.id
        return records

    def _perform_final_approval(self):
        self.ensure_one()
        employee = self.employee_id
        self.write(
            {
                # "original_job_id": employee.job_id.id,
                "original_department_id": employee.department_id.id,
                "original_parent_id": employee.parent_id.id,
                "original_branch_id": employee.branch_id.id,
                "original_division_id": employee.division_id.id,
                "original_cost_center_id": employee.cost_center_id.id,
            }
        )
        update_vals = {
            # "job_id": self.new_job_id.id,
            "department_id": self.new_department_id.id,
            "parent_id": self.new_parent_id.id,
            "branch_id": self.new_branch_id.id,
            "division_id": self.new_division_id.id,
            "cost_center_id": self.new_cost_center_id.id,
        }
        employee.write({k: v for k, v in update_vals.items() if v})

    def action_cancel(self):
        for rec in self:
            if rec.state == "approved":
                rec._revert_assignment()
            rec.state = "cancelled"
            if rec.activity_id:
                rec.activity_id.action_reject()

    def _revert_assignment(self):
        self.ensure_one()
        employee = self.employee_id
        update_vals = {
            # "job_id": self.original_job_id.id,
            "department_id": self.original_department_id.id,
            "parent_id": self.original_parent_id.id,
            "branch_id": self.original_branch_id.id,
            "division_id": self.original_division_id.id,
            "cost_center_id": self.original_cost_center_id.id,
        }
        employee.write(update_vals)

    @api.model
    def _check_end_of_temporary_assignments(self):
        today = fields.Date.today()
        assignments_to_end = self.search(
            [("state", "=", "approved"), ("end_date", "<=", today)]
        )
        for assignment in assignments_to_end:
            assignment._revert_assignment()
            assignment.state = "completed"
            if assignment.activity_id:
                assignment.activity_id.write({"state": "approved"})
