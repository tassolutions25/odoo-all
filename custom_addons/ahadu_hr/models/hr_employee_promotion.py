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

    # Current Fields
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
        "hr.branch", string="Current Branch", compute="_compute_current_fields"
    )
    current_cost_center_id = fields.Many2one(
        "hr.cost.center",
        string="Current Cost Center",
        compute="_compute_current_fields",
    )
    current_parent_id = fields.Many2one(
        "hr.employee",
        string="Current Manager",
        related="employee_id.parent_id",
        readonly=True,
    )
    current_salary = fields.Float(
        string="Current Salary", compute="_compute_current_fields"
    )
    current_transport_allowance_liters = fields.Float(
        string="Current Transport Allowance (Liters)",
        compute="_compute_current_fields",
        readonly=True,
    )
    current_hardship_allowance_level_id = fields.Many2one(
        "hr.hardship.allowance.level",
        string="Current Hardship Allowance Level",
        compute="_compute_current_fields",
        readonly=True,
    )
    current_representation_allowance = fields.Float(
        string="Current Representation Allowance (%)",
        compute="_compute_current_fields",
        readonly=True,
    )
    current_mobile_allowance = fields.Monetary(
        string="Current Mobile Allowance",
        compute="_compute_current_fields",
        currency_field="currency_id",
        readonly=True,
    )
    current_housing_allowance = fields.Monetary(
        string="Current Housing Allowance",
        compute="_compute_current_fields",
        currency_field="currency_id",
        readonly=True,
    )

    # New Fields
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
    attachment_ids = fields.Many2many(
        "ir.attachment",
        string="Attachments",
        help="Upload supporting documents like notices, letters, or certificates.",
    )
    activity_id = fields.Many2one(
        "hr.employee.activity", string="Activity Record", ondelete="set null"
    )

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
                rec.current_parent_id = employee.parent_id.id
                rec.current_salary = employee.emp_wage
                rec.current_transport_allowance_liters = (
                    employee.transport_allowance_liters
                )
                rec.current_hardship_allowance_level_id = (
                    employee.hardship_allowance_level_id
                )
                rec.current_representation_allowance = employee.representation_allowance
                rec.current_mobile_allowance = employee.mobile_allowance
                rec.current_housing_allowance = employee.housing_allowance
            else:
                rec.current_job_id = False
                rec.current_department_id = False
                rec.current_grade_id = False
                rec.current_division_id = False
                rec.current_branch_id = False
                rec.current_cost_center_id = False
                rec.current_salary = 0.0
                rec.current_transport_allowance_liters = 0.0
                rec.current_hardship_allowance_level_id = False
                rec.current_representation_allowance = 0.0
                rec.current_mobile_allowance = 0.0
                rec.current_housing_allowance = 0.0

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
            # Name -> ID: Update search field when employee is selected
            if rec.employee_id:
                rec.employee_number_search = rec.employee_id.employee_id

    def _inverse_employee_number_search(self):
        for rec in self:
            if rec.employee_number_search:
                rec._sync_employee_data()

    @api.onchange("employee_number_search")
    def _onchange_employee_number_search(self):
        # ID -> Name: Instant UI sync when typing ID
        if self.employee_number_search:
            self._sync_employee_data()

    def _sync_employee_data(self):
        """Helper to find employee by ID string"""
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

    # @api.onchange("employee_id", "employee_number_search")
    # def _onchange_employee_allowances(self):
    #     for rec in self:
    #         if rec.employee_id:
    #             rec.new_transport_allowance_liters = (
    #                 rec.employee_id.transport_allowance_liters
    #             )
    #             rec.new_hardship_allowance_level_id = (
    #                 rec.employee_id.hardship_allowance_level_id
    #             )
    #             rec.new_representation_allowance = (
    #                 rec.employee_id.representation_allowance
    #             )
    #             rec.new_mobile_allowance = rec.employee_id.mobile_allowance
    #             rec.new_housing_allowance = rec.employee_id.housing_allowance

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("employee_id"):
                employee = self.env["hr.employee"].browse(vals["employee_id"])
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
        if self.new_division_id and hasattr(self.employee_id, "division_id"):
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
