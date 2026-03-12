from odoo import models, fields, api, _


class HrEmployeeTransfer(models.Model):
    _name = "hr.employee.transfer"
    _description = "Employee Transfer (Location Change)"
    _order = "transfer_date desc"
    _inherit = ["mail.thread", "mail.activity.mixin", "hr.approval.mixin"]

    name = fields.Char(string="Reference", compute="_compute_name", store=True)
    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)
    transfer_date = fields.Date(
        string="Transfer Date", required=True, default=fields.Date.today
    )
    current_branch_id = fields.Many2one(
        "hr.branch",
        string="Current Branch",
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
    current_cost_center_id = fields.Many2one(
        "hr.cost.center",
        string="Current Cost Center",
        compute="_compute_current_fields",
        readonly=True,
    )
    current_manager_id = fields.Many2one(
        "res.users",
        string="Current Manager",
        compute="_compute_current_fields",
        readonly=True,
    )
    current_job_id = fields.Many2one(
        "hr.job",
        string="Current Position",
        compute="_compute_current_fields",
        readonly=True,
    )
    new_branch_id = fields.Many2one("hr.branch", string="New Branch", required=True)
    new_department_id = fields.Many2one("hr.department", string="New Department")
    new_division_id = fields.Many2one("hr.division", string="New Division")
    new_cost_center_id = fields.Many2one("hr.cost.center", string="New Cost Center")
    new_manager_id = fields.Many2one("res.users", string="New Manager")
    new_job_id = fields.Many2one("hr.job", string="New Position")
    reason = fields.Text(string="Reason for Transfer")
    activity_id = fields.Many2one(
        "hr.employee.activity", string="Activity Record", ondelete="set null"
    )

    @api.depends("employee_id")
    def _compute_name(self):
        for rec in self:
            rec.name = (
                f"Transfer for {rec.employee_id.name}"
                if rec.employee_id
                else _("New Transfer")
            )

    @api.depends("employee_id")
    def _compute_current_fields(self):
        for rec in self:
            if rec.employee_id:
                employee = rec.employee_id
                rec.current_branch_id = employee.branch_id.id
                rec.current_department_id = employee.department_id.id
                rec.current_division_id = employee.division_id.id
                rec.current_cost_center_id = (
                    employee.cost_center_id.id
                    if hasattr(employee, "cost_center_id")
                    else False
                )
                rec.current_job_id = employee.job_id.id
                if employee.parent_id and employee.parent_id.user_id:
                    rec.current_manager_id = employee.parent_id.user_id.id
                else:
                    rec.current_manager_id = False
            else:
                rec.current_branch_id = False
                rec.current_department_id = False
                rec.current_division_id = False
                rec.current_cost_center_id = False
                rec.current_manager_id = False
                rec.current_job_id = False

    @api.model_create_multi
    def create(self, vals_list):
        transfers = super().create(vals_list)
        for transfer in transfers:
            activity_vals = {
                "employee_id": transfer.employee_id.id,
                "activity_type": "transfer",
                "date": transfer.transfer_date,
                "transfer_id": transfer.id,
                "description": f"Transfer from {transfer.employee_id.branch_id.name or 'N/A'} to {transfer.new_branch_id.name}",
            }
            activity = self.env["hr.employee.activity"].create(activity_vals)
            transfer.activity_id = activity.id
        return transfers

    def _perform_final_approval(self):
        self.ensure_one()
        update_vals = {"branch_id": self.new_branch_id.id}
        if self.new_department_id:
            update_vals["department_id"] = self.new_department_id.id
        if self.new_division_id:
            update_vals["division_id"] = self.new_division_id.id
        if self.new_cost_center_id and hasattr(self.employee_id, "cost_center_id"):
            update_vals["cost_center_id"] = self.new_cost_center_id.id
        if self.new_manager_id:
            update_vals["parent_id"] = self.new_manager_id.id
        if self.new_job_id:
            update_vals["job_id"] = self.new_job_id.id
        self.employee_id.write(update_vals)
