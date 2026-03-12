from odoo import models, fields, api, _


class HrEmployeeRetirement(models.Model):
    _name = "hr.employee.retirement"
    _description = "Employee Retirement"
    _order = "retirement_date desc"
    _inherit = ["hr.approval.mixin"]

    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)
    retirement_date = fields.Date(string="Retirement Date", required=True)
    retirement_type = fields.Selection(
        [
            ("normal", "Normal Retirement"),
            ("early", "Early Retirement"),
            ("medical", "Medical Retirement"),
        ],
        string="Retirement Type",
        required=True,
    )
    years_of_service = fields.Float(
        string="Years of Service", compute="_compute_retirement_details", store=True
    )
    final_salary = fields.Float(
        string="Final Salary", compute="_compute_retirement_details", store=True
    )
    pension_amount = fields.Float(
        string="Pension Amount", compute="_compute_retirement_details", store=True
    )
    reason = fields.Text(string="Reason")
    activity_id = fields.Many2one(
        "hr.employee.activity", string="Activity Record", ondelete="set null"
    )

    @api.depends("employee_id", "retirement_date")
    def _compute_retirement_details(self):
        for rec in self:
            years, salary, pension = 0.0, 0.0, 0.0
            if rec.employee_id and rec.retirement_date:
                if rec.employee_id.date_of_joining:
                    delta = rec.retirement_date - rec.employee_id.date_of_joining
                    years = delta.days / 365.25
                if rec.employee_id.contract_id:
                    salary = rec.employee_id.contract_id.wage
                if years > 0 and salary > 0:
                    pension = 0.02 * years * salary  # Placeholder calculation
            rec.years_of_service = years
            rec.final_salary = salary
            rec.pension_amount = pension

    @api.model_create_multi
    def create(self, vals_list):
        retirements = super().create(vals_list)
        for retirement in retirements:
            activity_vals = {
                "employee_id": retirement.employee_id.id,
                "activity_type": "retirement",
                "date": retirement.retirement_date,
                "retirement_id": retirement.id,
                "description": f"Retirement - {dict(self._fields['retirement_type'].selection).get(retirement.retirement_type)}",
            }
            activity = self.env["hr.employee.activity"].create(activity_vals)
            retirement.activity_id = activity.id
        return retirements

    def _perform_final_approval(self):
        self.ensure_one()
        self.employee_id.write(
            {"active": False, "departure_date": self.retirement_date}
        )
