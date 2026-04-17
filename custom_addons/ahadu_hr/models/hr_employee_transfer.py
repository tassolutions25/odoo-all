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

    # SNAPSHOT FIELDS (History) - Changed Manager fields to hr.employee
    current_branch_id = fields.Many2one(
        "hr.branch", string="Previous Branch", readonly=True
    )
    current_department_id = fields.Many2one(
        "hr.department", string="Previous Department", readonly=True
    )
    current_division_id = fields.Many2one(
        "hr.division", string="Previous Division", readonly=True
    )
    current_cost_center_id = fields.Many2one(
        "hr.cost.center", string="Previous Cost Center", readonly=True
    )
    current_manager_id = fields.Many2one(
        "hr.employee", string="Previous Manager", readonly=True
    )
    current_job_id = fields.Many2one(
        "hr.job", string="Previous Position", readonly=True
    )

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

    # NEW INFORMATION
    new_branch_id = fields.Many2one("hr.branch", string="New Branch", required=True)
    new_department_id = fields.Many2one("hr.department", string="New Department")
    new_division_id = fields.Many2one("hr.division", string="New Division")
    new_cost_center_id = fields.Many2one("hr.cost.center", string="New Cost Center")
    new_manager_id = fields.Many2one("hr.employee", string="New Manager")
    new_job_id = fields.Many2one("hr.job", string="New Position")

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
    reason = fields.Text(string="Reason for Transfer")
    attachment_ids = fields.Many2many("ir.attachment", string="Attachments")
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
        else:
            self.employee_id = False

    @api.onchange("employee_id", "employee_number_search")
    def _onchange_employee_id_fetch_history(self):
        """Instantly fetch all current data into the form view for history."""
        if self.employee_id:
            emp = self.employee_id
            self.current_branch_id = emp.branch_id
            self.current_department_id = emp.department_id
            self.current_division_id = emp.division_id
            self.current_cost_center_id = emp.cost_center_id
            self.current_job_id = emp.job_id
            self.current_manager_id = emp.parent_id

            # Allowances
            self.current_housing_allowance = emp.housing_allowance
            self.current_mobile_allowance = emp.mobile_allowance
            self.current_transport_allowance_liters = emp.transport_allowance_liters
            self.current_representation_allowance = emp.representation_allowance
            self.current_hardship_allowance_level_id = emp.hardship_allowance_level_id

            # Pre-fill 'New' fields with current values to make editing easier
            if not self.new_branch_id:
                self.new_branch_id = emp.branch_id
            if not self.new_department_id:
                self.new_department_id = emp.department_id
            if not self.new_job_id:
                self.new_job_id = emp.job_id

            # Pre-fill allowances in 'New' section
            self.new_housing_allowance = emp.housing_allowance
            self.new_mobile_allowance = emp.mobile_allowance
            self.new_transport_allowance_liters = emp.transport_allowance_liters
            self.new_representation_allowance = emp.representation_allowance
            self.new_hardship_allowance_level_id = emp.hardship_allowance_level_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("employee_id"):
                employee = self.env["hr.employee"].browse(vals["employee_id"])
                # SNAPSHOT: Permanently save current state into history fields
                vals.update(
                    {
                        "current_branch_id": employee.branch_id.id,
                        "current_department_id": employee.department_id.id,
                        "current_division_id": employee.division_id.id,
                        "current_cost_center_id": employee.cost_center_id.id,
                        "current_job_id": employee.job_id.id,
                        "current_manager_id": employee.parent_id.id,
                        "current_housing_allowance": employee.housing_allowance,
                        "current_mobile_allowance": employee.mobile_allowance,
                        "current_transport_allowance_liters": employee.transport_allowance_liters,
                        "current_representation_allowance": employee.representation_allowance,
                        "current_hardship_allowance_level_id": employee.hardship_allowance_level_id.id,
                    }
                )

        transfers = super().create(vals_list)
        for transfer in transfers:
            activity_vals = {
                "employee_id": transfer.employee_id.id,
                "activity_type": "transfer",
                "date": transfer.transfer_date,
                "transfer_id": transfer.id,
                "description": f"Transfer from {transfer.current_branch_id.name or 'N/A'} to {transfer.new_branch_id.name}",
            }
            activity = self.env["hr.employee.activity"].create(activity_vals)
            transfer.activity_id = activity.id
        return transfers

    def _perform_final_approval(self):
        self.ensure_one()
        update_vals = {
            "branch_id": self.new_branch_id.id,
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
        if self.new_cost_center_id:
            update_vals["cost_center_id"] = self.new_cost_center_id.id
        if self.new_manager_id:
            # FIX: Points to parent_id (hr.employee), not user_id
            update_vals["parent_id"] = self.new_manager_id.id
        if self.new_job_id:
            update_vals["job_id"] = self.new_job_id.id

        self.employee_id.write(update_vals)
