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
        "hr.branch", string="Current Branch", compute="_compute_current_fields"
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

    new_job_id = fields.Many2one("hr.job", string="New Position", required=True)
    new_grade_id = fields.Many2one("hr.grade", string="New Grade", required=True)
    new_branch_id = fields.Many2one("hr.branch", string="New Branch")
    new_department_id = fields.Many2one("hr.department", string="New Department")
    new_division_id = fields.Many2one("hr.division", string="New Division")
    new_cost_center_id = fields.Many2one("hr.cost.center", string="New Cost Center")
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
    approve_uid = fields.Many2one(
        "res.users", string="Approved By", tracking=True, readonly=True, copy=False
    )
    reason = fields.Text(string="Reason for Demotion", required=True)
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
                rec.current_job_id = employee.job_id.id
                rec.current_department_id = employee.department_id.id
                rec.current_division_id = employee.division_id.id
                rec.current_grade_id = employee.grade_id.id
                rec.current_branch_id = employee.branch_id.id
                rec.current_cost_center_id = employee.cost_center_id.id
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
                rec.current_division_id = False
                rec.current_grade_id = False
                rec.current_branch_id = False
                rec.current_cost_center_id = False
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

    @api.onchange("employee_id", "employee_number_search")
    def _onchange_employee_allowances(self):
        for rec in self:
            if rec.employee_id:
                rec.new_transport_allowance_liters = (
                    rec.employee_id.transport_allowance_liters
                )
                rec.new_hardship_allowance_level_id = (
                    rec.employee_id.hardship_allowance_level_id
                )
                rec.new_representation_allowance = (
                    rec.employee_id.representation_allowance
                )
                rec.new_mobile_allowance = rec.employee_id.mobile_allowance
                rec.new_housing_allowance = rec.employee_id.housing_allowance

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

    def _perform_final_approval(self):
        self.ensure_one()
        employee_vals = {
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
            employee_vals["department_id"] = self.new_department_id.id
        if self.new_division_id and hasattr(self.employee_id, "division_id"):
            employee_vals["division_id"] = self.new_division_id.id
        if self.new_branch_id:
            employee_vals["branch_id"] = self.new_branch_id.id
        if self.new_cost_center_id:
            employee_vals["cost_center_id"] = self.new_cost_center_id.id

        self.employee_id.write(employee_vals)
