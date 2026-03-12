from odoo import models, fields, api, _


class HrEmployeeLateral(models.Model):
    _name = "hr.employee.lateral"
    _description = "Employee Lateral Move (Role Change)"
    _order = "lateral_date desc"
    _inherit = ["hr.approval.mixin"]

    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)
    lateral_date = fields.Date(
        string="Lateral Date", required=True, default=fields.Date.today
    )
    current_department_id = fields.Many2one(
        "hr.department",
        string="Current Department",
        compute="_compute_current_fields",
        readonly=True,
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
    current_branch_id = fields.Many2one(
        "hr.branch",
        string="Current Branch",
        compute="_compute_current_fields",
        readonly=True,
    )
    new_department_id = fields.Many2one(
        "hr.department", string="New Department", required=True
    )
    new_job_id = fields.Many2one("hr.job", string="New Position", required=True)
    new_grade_id = fields.Many2one(
        "hr.grade",
        string="Grade (Unchanged)",
        compute="_compute_current_fields",
        readonly=True,
        store=True,
    )
    new_branch_id = fields.Many2one(
        "hr.branch",
        string="New Branch (If changing)",
        help="Leave blank if the employee is not changing location.",
    )
    reason = fields.Text(string="Reason for Lateral Movement")
    attachment_ids = fields.Many2many("ir.attachment", string="Attachments")
    activity_id = fields.Many2one(
        "hr.employee.activity", string="Activity Record", ondelete="set null"
    )

    @api.depends("employee_id")
    def _compute_current_fields(self):
        for rec in self:
            if rec.employee_id:
                employee = rec.employee_id
                rec.current_department_id = employee.department_id.id
                rec.current_job_id = employee.job_id.id
                rec.current_grade_id = employee.grade_id.id
                rec.current_branch_id = employee.branch_id.id
                rec.new_grade_id = employee.grade_id.id
            else:
                rec.current_department_id = False
                rec.current_job_id = False
                rec.current_grade_id = False
                rec.current_branch_id = False
                rec.new_grade_id = False

    @api.model_create_multi
    def create(self, vals_list):
        laterals = super().create(vals_list)
        for lateral in laterals:
            activity_vals = {
                "employee_id": lateral.employee_id.id,
                "activity_type": "lateral",
                "date": lateral.lateral_date,
                "lateral_id": lateral.id,
                "description": f"Lateral move to {lateral.new_job_id.name}",
            }
            activity = self.env["hr.employee.activity"].create(activity_vals)
            lateral.activity_id = activity.id
        return laterals

    def _perform_final_approval(self):
        self.ensure_one()
        update_vals = {
            "job_id": self.new_job_id.id,
            "department_id": self.new_department_id.id,
        }
        if self.new_branch_id:
            update_vals["branch_id"] = self.new_branch_id.id
        self.employee_id.write(update_vals)
