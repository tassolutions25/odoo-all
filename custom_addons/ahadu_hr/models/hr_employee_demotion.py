from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HrEmployeeDemotion(models.Model):
    _name = "hr.employee.demotion"
    _description = "Employee Demotion"
    _order = "demotion_date desc"
    _inherit = ["mail.thread", "mail.activity.mixin", "hr.approval.mixin"]

    name = fields.Char(string="Reference", compute="_compute_name", store=True)
    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)
    demotion_date = fields.Date(
        string="Demotion Date", required=True, default=fields.Date.today
    )
    current_job_id = fields.Many2one(
        "hr.job", string="Current Position", compute="_compute_current_fields"
    )
    current_grade_id = fields.Many2one(
        "hr.grade", string="Current Grade", compute="_compute_current_fields"
    )
    current_branch_id = fields.Many2one(
        "hr.branch",
        string="Current Branch",
        compute="_compute_current_fields",
    )
    current_department_id = fields.Many2one(
        "hr.department", string="Current Department", compute="_compute_current_fields"
    )
    current_division_id = fields.Many2one(
        "hr.division", string="Current Division", compute="_compute_current_fields"
    )
    current_cost_center_id = fields.Many2one(
        "hr.cost.center",
        string="Current Cost Center",
        compute="_compute_current_fields",
    )
    new_job_id = fields.Many2one("hr.job", string="New Position", required=True)
    new_grade_id = fields.Many2one("hr.grade", string="New Grade", required=True)
    new_branch_id = fields.Many2one("hr.branch", string="New Branch")
    new_department_id = fields.Many2one("hr.department", string="New Department")
    new_division_id = fields.Many2one("hr.division", string="New Division")
    new_cost_center_id = fields.Many2one("hr.cost.center", string="New Cost Center")
    currency_id = fields.Many2one(related="employee_id.currency_id")
    approve_uid = fields.Many2one(
        "res.users", string="Approved By", tracking=True, readonly=True, copy=False
    )
    reason = fields.Text(string="Reason for Demotion", required=True)
    activity_id = fields.Many2one(
        "hr.employee.activity",
        string="Activity Record",
        ondelete="set null",
        readonly=True,
    )

    @api.depends("employee_id")
    def _compute_name(self):
        for rec in self:
            rec.name = (
                f"Demotion for {rec.employee_id.name}"
                if rec.employee_id
                else _("New Demotion")
            )

    @api.depends("employee_id")
    def _compute_current_fields(self):
        for rec in self:
            if rec.employee_id:
                employee = rec.employee_id
                contract = employee.contract_id
                rec.current_job_id = employee.job_id.id
                rec.current_department_id = employee.department_id.id
                rec.current_division_id = employee.division_id.id
                rec.current_grade_id = employee.grade_id.id
                rec.current_branch_id = employee.branch_id.id
                rec.current_cost_center_id = employee.cost_center_id.id
            else:
                rec.current_job_id = False
                rec.current_department_id = False
                rec.current_division_id = False
                rec.current_grade_id = False
                rec.current_branch_id = False
                rec.current_cost_center_id = False

    @api.model_create_multi
    def create(self, vals_list):
        demotions = super().create(vals_list)
        for demotion in demotions:
            activity_vals = {
                "employee_id": demotion.employee_id.id,
                "activity_type": "demotion",
                "date": demotion.demotion_date,
                "demotion_id": demotion.id,
                "description": f"Demotion to {demotion.new_job_id.name}",
            }
            activity = self.env["hr.employee.activity"].create(activity_vals)
            demotion.activity_id = activity.id
        return demotions

    # --- Mixin Implementation ---
    def _perform_final_approval(self):
        self.ensure_one()
        employee_vals = {"job_id": self.new_job_id.id, "grade_id": self.new_grade_id.id}
        if self.new_department_id:
            employee_vals["department_id"] = self.new_department_id.id
        if self.new_division_id and hasattr(self.employee_id, "division_id"):
            employee_vals["division_id"] = self.new_division_id.id
        if self.new_branch_id:
            employee_vals["branch_id"] = self.new_branch_id.id
        if self.new_cost_center_id:
            employee_vals["cost_center_id"] = self.new_cost_center_id.id

        self.employee_id.write(employee_vals)
