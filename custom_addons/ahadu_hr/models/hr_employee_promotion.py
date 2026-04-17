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

    # CHANGED: These are now regular stored fields to preserve history snapshot
    current_job_id = fields.Many2one(
        "hr.job", string="Previous Position", readonly=True
    )
    current_grade_id = fields.Many2one(
        "hr.grade", string="Previous Grade", readonly=True
    )
    current_department_id = fields.Many2one(
        "hr.department", string="Previous Department", readonly=True
    )
    current_division_id = fields.Many2one(
        "hr.division", string="Previous Division", readonly=True
    )
    current_branch_id = fields.Many2one(
        "hr.branch", string="Previous Branch", readonly=True
    )
    current_cost_center_id = fields.Many2one(
        "hr.cost.center", string="Previous Cost Center", readonly=True
    )
    current_parent_id = fields.Many2one(
        "hr.employee", string="Previous Manager", readonly=True
    )
    current_salary = fields.Float(string="Previous Salary", readonly=True)

    current_transport_allowance_liters = fields.Float(
        string="Previous Transport (Liters)", readonly=True
    )
    current_hardship_allowance_level_id = fields.Many2one(
        "hr.hardship.allowance.level", string="Previous Hardship Level", readonly=True
    )
    current_representation_allowance = fields.Float(
        string="Previous Representation (%)", readonly=True
    )
    current_mobile_allowance = fields.Monetary(
        string="Previous Mobile Allowance", currency_field="currency_id", readonly=True
    )
    current_housing_allowance = fields.Monetary(
        string="Previous Housing Allowance", currency_field="currency_id", readonly=True
    )

    new_job_id = fields.Many2one("hr.job", string="New Position", required=True)
    new_grade_id = fields.Many2one("hr.grade", string="New Grade", required=True)
    new_department_id = fields.Many2one("hr.department", string="New Department")
    new_division_id = fields.Many2one("hr.division", string="New Division")
    new_branch_id = fields.Many2one("hr.branch", string="New Branch")
    new_cost_center_id = fields.Many2one("hr.cost.center", string="New Cost Center")
    new_parent_id = fields.Many2one("hr.employee", string="New Manager")
    new_salary = fields.Float(string="New Salary", tracking=True)

    new_transport_allowance_liters = fields.Float(
        string="New Transport Allowance (Liters)", tracking=True
    )
    new_hardship_allowance_level_id = fields.Many2one(
        "hr.hardship.allowance.level",
        string="New Hardship Allowance Level",
        tracking=True,
    )
    new_representation_allowance = fields.Float(
        string="New Representation Allowance (%)", tracking=True
    )
    new_mobile_allowance = fields.Monetary(
        string="New Mobile Allowance", tracking=True, currency_field="currency_id"
    )
    new_housing_allowance = fields.Monetary(
        string="New Housing Allowance", tracking=True, currency_field="currency_id"
    )

    currency_id = fields.Many2one(related="employee_id.currency_id")
    reason = fields.Text(string="Reason for Promotion")
    attachment_ids = fields.Many2many("ir.attachment", string="Attachments")
    activity_id = fields.Many2one(
        "hr.employee.activity", string="Activity Record", ondelete="set null"
    )

    @api.onchange("employee_id")
    def _onchange_employee_id_fetch_history(self):
        if self.employee_id:
            emp = self.employee_id
            # Structure
            self.current_job_id = emp.job_id
            self.current_grade_id = emp.grade_id
            self.current_department_id = emp.department_id
            self.current_division_id = (
                emp.division_id if hasattr(emp, "division_id") else False
            )
            self.current_branch_id = emp.branch_id
            self.current_cost_center_id = emp.cost_center_id
            self.current_parent_id = emp.parent_id
            self.current_salary = emp.emp_wage

            # SNAPSHOT ALLOWANCES
            self.current_housing_allowance = emp.housing_allowance
            self.current_mobile_allowance = emp.mobile_allowance
            self.current_transport_allowance_liters = emp.transport_allowance_liters
            self.current_representation_allowance = emp.representation_allowance
            self.current_hardship_allowance_level_id = emp.hardship_allowance_level_id

    @api.depends("employee_id")
    def _compute_name(self):
        for rec in self:
            rec.name = (
                f"Promotion for {rec.employee_id.name}"
                if rec.employee_id
                else _("New Promotion")
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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("employee_id"):
                employee = self.env["hr.employee"].browse(vals["employee_id"])

                # SNAPSHOT: Capture current state into history fields
                vals.update(
                    {
                        "current_job_id": employee.job_id.id,
                        "current_department_id": employee.department_id.id,
                        "current_grade_id": employee.grade_id.id,
                        "current_branch_id": employee.branch_id.id,
                        "current_division_id": (
                            employee.division_id.id
                            if hasattr(employee, "division_id")
                            else False
                        ),
                        "current_cost_center_id": employee.cost_center_id.id,
                        "current_parent_id": employee.parent_id.id,
                        "current_salary": employee.emp_wage,
                        "current_transport_allowance_liters": employee.transport_allowance_liters,
                        "current_hardship_allowance_level_id": employee.hardship_allowance_level_id.id,
                        "current_representation_allowance": employee.representation_allowance,
                        "current_mobile_allowance": employee.mobile_allowance,
                        "current_housing_allowance": employee.housing_allowance,
                    }
                )

                if "new_transport_allowance_liters" not in vals:
                    vals["new_transport_allowance_liters"] = (
                        employee.transport_allowance_liters
                    )
                if "new_hardship_allowance_level_id" not in vals:
                    vals["new_hardship_allowance_level_id"] = (
                        employee.hardship_allowance_level_id.id
                        if employee.hardship_allowance_level_id
                        else False
                    )
                if "new_representation_allowance" not in vals:
                    vals["new_representation_allowance"] = (
                        employee.representation_allowance
                    )
                if "new_mobile_allowance" not in vals:
                    vals["new_mobile_allowance"] = employee.mobile_allowance
                if "new_housing_allowance" not in vals:
                    vals["new_housing_allowance"] = employee.housing_allowance

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

    def _perform_final_approval(self):
        self.ensure_one()
        update_vals = {
            "job_id": self.new_job_id.id,
            "grade_id": self.new_grade_id.id,
            "transport_allowance_liters": self.new_transport_allowance_liters,
            "hardship_allowance_level_id": (
                self.new_hardship_allowance_level_id.id
                if self.new_hardship_allowance_level_id
                else False
            ),
            "representation_allowance": self.new_representation_allowance,
            "mobile_allowance": self.new_mobile_allowance,
            "housing_allowance": self.new_housing_allowance,
        }
        if self.new_department_id:
            update_vals["department_id"] = self.new_department_id.id
        if self.new_division_id:
            update_vals["division_id"] = self.new_division_id.id
        if self.new_branch_id:
            update_vals["branch_id"] = self.new_branch_id.id
        if self.new_cost_center_id:
            update_vals["cost_center_id"] = self.new_cost_center_id.id
        if self.new_parent_id:
            self.employee_id.sudo().write({"parent_id": self.new_parent_id.id})
        if self.new_salary > 0:
            update_vals["emp_wage"] = self.new_salary

        self.employee_id.write(update_vals)
