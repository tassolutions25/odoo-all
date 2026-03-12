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

    # Current Status (Computed)
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

    # New Status
    new_wage = fields.Monetary(
        string="New Base Salary",
        required=True,
        tracking=True,
        currency_field="currency_id",
    )

    # While CTC usually changes salary, sometimes metadata changes with it
    new_grade_id = fields.Many2one("hr.grade", string="New Grade")
    new_job_id = fields.Many2one("hr.job", string="New Position")
    new_department_id = fields.Many2one("hr.department", string="New Department")

    currency_id = fields.Many2one(related="employee_id.currency_id")
    reason = fields.Text(string="Reason for Adjustment")

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
            else:
                rec.current_job_id = False
                rec.current_department_id = False
                rec.current_grade_id = False
                rec.current_wage = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        ctc_adjustments = super(
            HrEmployeeCtc,
            self.with_context(tracking_disable=True, mail_create_nolog=True),
        ).create(vals_list)

        # Batch create activities to avoid multiple write loops
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

    # --- Approval Mixin Implementation ---
    def _perform_final_approval(self):
        self.ensure_one()

        update_vals = {"emp_wage": self.new_wage}

        # Optionally update other fields if they were set during the CTC change
        if self.new_grade_id:
            update_vals["grade_id"] = self.new_grade_id.id
        if self.new_job_id:
            update_vals["job_id"] = self.new_job_id.id
        if self.new_department_id:
            update_vals["department_id"] = self.new_department_id.id

        self.employee_id.write(update_vals)

        # If using contracts, update the active contract wage as well
        if self.employee_id.contract_id:
            self.employee_id.contract_id.write({"wage": self.new_wage})

    def action_submit(self):
        # Override if specific submission logic is needed, otherwise mixin handles it
        return super().action_submit()
