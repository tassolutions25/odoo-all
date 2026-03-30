from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HrEmployeeCtc(models.Model):
    _name = "hr.employee.ctc"
    _description = "Employee CTC Adjustment"
    _order = "date desc"
    _inherit = ["mail.thread", "mail.activity.mixin", "hr.approval.mixin"]

    name = fields.Char(string="Reference", compute="_compute_name", store=True)
    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)
    date = fields.Date(
        string="Effective Date", required=True, default=fields.Date.today
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
    current_wage = fields.Monetary(
        string="Current Base Salary",
        compute="_compute_current_fields",
        currency_field="currency_id",
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

    new_wage = fields.Monetary(
        string="New Base Salary",
        required=True,
        tracking=True,
        currency_field="currency_id",
    )
    new_grade_id = fields.Many2one("hr.grade", string="New Grade")
    new_job_id = fields.Many2one("hr.job", string="New Position")
    new_department_id = fields.Many2one("hr.department", string="New Department")
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
    reason = fields.Text(string="Reason for Adjustment")
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
                f"CTC Adjustment for {rec.employee_id.name}"
                if rec.employee_id
                else _("New CTC Adjustment")
            )

    @api.depends("employee_id")
    def _compute_current_fields(self):
        for rec in self:
            if rec.employee_id:
                employee = rec.employee_id
                rec.current_job_id = employee.job_id.id
                rec.current_department_id = employee.department_id.id
                rec.current_grade_id = (
                    employee.grade_id.id if employee.grade_id else False
                )
                rec.current_wage = employee.emp_wage
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
                rec.current_wage = 0.0
                rec.current_transport_allowance_liters = 0.0
                rec.current_hardship_allowance_level_id = False
                rec.current_representation_allowance = 0.0
                rec.current_mobile_allowance = 0.0
                rec.current_housing_allowance = 0.0

    employee_number_search = fields.Char(string="Employee ID", store=False)

    @api.onchange("employee_number_search")
    def _onchange_employee_number_search(self):
        if self.employee_number_search:
            employee = self.env["hr.employee"].search(
                [("employee_id", "=ilike", self.employee_number_search.strip())],
                limit=1,
            )

            if employee:
                self.employee_id = employee
            else:
                self.employee_id = False

    @api.onchange("employee_id")
    def _onchange_employee_id_sync(self):
        if self.employee_id:
            self.employee_number_search = self.employee_id.employee_id
        else:
            self.employee_number_search = False

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

        ctc_adjustments = super(
            HrEmployeeCtc,
            self.with_context(tracking_disable=True, mail_create_nolog=True),
        ).create(vals_list)

        activity_vals_list = []
        for ctc in ctc_adjustments:
            activity_vals_list.append(
                {
                    "employee_id": ctc.employee_id.id,
                    "activity_type": "ctc",
                    "date": ctc.date,
                    "ctc_id": ctc.id,
                    "description": f"Salary Adjustment to {ctc.new_wage}",
                    "state": "approved",
                }
            )

        if activity_vals_list:
            activities = self.env["hr.employee.activity"].create(activity_vals_list)
            for ctc, activity in zip(ctc_adjustments, activities):
                ctc.activity_id = activity.id

        return ctc_adjustments

    def _perform_final_approval(self):
        self.ensure_one()

        update_vals = {
            "emp_wage": self.new_wage,
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

        if self.new_grade_id:
            update_vals["grade_id"] = self.new_grade_id.id
        if self.new_job_id:
            update_vals["job_id"] = self.new_job_id.id
        if self.new_department_id:
            update_vals["department_id"] = self.new_department_id.id

        self.employee_id.write(update_vals)

        if self.employee_id.contract_id:
            self.employee_id.contract_id.write({"wage": self.new_wage})

    def action_submit(self):
        return super().action_submit()
