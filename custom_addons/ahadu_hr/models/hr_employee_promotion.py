from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HrEmployeePromotion(models.Model):
    _name = "hr.employee.promotion"
    _description = "Employee Promotion"
    _order = "promotion_date desc"
    _inherit = ["mail.thread", "mail.activity.mixin", "hr.approval.mixin"]

    name = fields.Char(string="Reference", compute="_compute_name", store=True)
    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)
    promotion_date = fields.Date(
        string="Promotion Date", required=True, default=fields.Date.today
    )
    current_job_id = fields.Many2one(
        "hr.job",
        string="Current Position",
        compute="_compute_current_fields",
        readonly=True,
    )
    current_grade_id = fields.Many2one(
        "hr.grade",
        string="Current Grade",
        compute="_compute_current_fields",
        readonly=True,
    )
    current_department_id = fields.Many2one(
        "hr.department",
        string="Current Department",
        compute="_compute_current_fields",
        readonly=True,
    )
    current_division_id = fields.Many2one(
        "hr.division",
        string="Current Division",
        compute="_compute_current_fields",
        readonly=True,
    )
    current_branch_id = fields.Many2one(
        "hr.branch",
        string="Current Branch",
        compute="_compute_current_fields",
    )
    current_cost_center_id = fields.Many2one(
        "hr.cost.center",
        string="Current Cost Center",
        compute="_compute_current_fields",
    )
    current_salary = fields.Float(
        string="Current Salary", compute="_compute_current_fields"
    )
    new_job_id = fields.Many2one("hr.job", string="New Position", required=True)
    new_grade_id = fields.Many2one("hr.grade", string="New Grade", required=True)
    new_department_id = fields.Many2one("hr.department", string="New Department")
    new_division_id = fields.Many2one("hr.division", string="New Division")
    new_branch_id = fields.Many2one("hr.branch", string="New Branch")
    new_cost_center_id = fields.Many2one("hr.cost.center", string="New Cost Center")
    new_salary = fields.Float(string="New Salary", tracking=True)
    currency_id = fields.Many2one(related="employee_id.currency_id")
    reason = fields.Text(string="Reason for Promotion")
    activity_id = fields.Many2one(
        "hr.employee.activity", string="Activity Record", ondelete="set null"
    )

    # state field is now inherited from hr.approval.mixin
    @api.depends("employee_id")
    def _compute_name(self):
        for rec in self:
            rec.name = (
                f"Promotion for {rec.employee_id.name}"
                if rec.employee_id
                else _("New Promotion")
            )

    @api.depends("employee_id")
    def _compute_current_fields(self):
        for rec in self:
            if rec.employee_id:
                employee = rec.employee_id
                contract = employee.contract_id
                rec.current_job_id = employee.job_id.id
                rec.current_department_id = employee.department_id.id
                rec.current_grade_id = employee.grade_id.id
                rec.current_division_id = (
                    employee.division_id.id
                    if hasattr(employee, "division_id")
                    else False
                )
                rec.current_branch_id = employee.branch_id.id
                rec.current_cost_center_id = employee.cost_center_id.id
                rec.current_salary = employee.emp_wage
            else:
                rec.current_job_id = False
                rec.current_department_id = False
                rec.current_grade_id = False
                rec.current_division_id = False
                rec.current_branch_id = False
                rec.current_cost_center_id = False
                rec.current_salary = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        promotions = super().create(vals_list)
        for promotion in promotions:
            activity_vals = {
                "employee_id": promotion.employee_id.id,
                "activity_type": "promotion",
                "date": promotion.promotion_date,
                "promotion_id": promotion.id,
                "description": f"Promotion to {promotion.new_job_id.name}",
            }
            activity = self.env["hr.employee.activity"].create(activity_vals)
            promotion.activity_id = activity.id
        return promotions

    # --- Mixin Implementation ---
    def _perform_final_approval(self):
        self.ensure_one()
        update_vals = {
            "job_id": self.new_job_id.id,
            "grade_id": self.new_grade_id.id,
        }
        if self.new_department_id:
            update_vals["department_id"] = self.new_department_id.id
        if self.new_division_id and hasattr(self.employee_id, "division_id"):
            update_vals["division_id"] = self.new_division_id.id
        if self.new_branch_id:
            update_vals["branch_id"] = self.new_branch_id.id
        if self.new_cost_center_id:
            update_vals["cost_center_id"] = self.new_cost_center_id.id
        if self.new_salary > 0:
            update_vals["emp_wage"] = self.new_salary

        self.employee_id.write(update_vals)
