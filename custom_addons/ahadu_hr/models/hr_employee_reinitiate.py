from odoo import models, fields, api, _


class HrEmployeeReinitiate(models.Model):
    _name = "hr.employee.reinitiate"
    _description = "Employee Reinitiate"
    _inherit = ["mail.thread", "mail.activity.mixin", "hr.approval.mixin"]
    _order = "date desc"

    # Allow domain to include inactive (archived) employees
    employee_id = fields.Many2one(
        "hr.employee",
        string="Employee",
        required=True,
        domain="['|', ('active', '=', False), ('active', '=', True)]",
    )
    date = fields.Date(string="Date", default=fields.Date.today, required=True)
    reason = fields.Text(string="Reason")
    activity_id = fields.Many2one("hr.employee.activity", string="Activity Record")

    employee_number_search = fields.Char(string="Employee ID", store=False)

    @api.onchange("employee_number_search")
    def _onchange_employee_number_search(self):
        if self.employee_number_search:
            # We MUST use with_context(active_test=False) so it can find archived employees
            employee = (
                self.env["hr.employee"]
                .with_context(active_test=False)
                .search(
                    [("employee_id", "=ilike", self.employee_number_search.strip())],
                    limit=1,
                )
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

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            activity = self.env["hr.employee.activity"].create(
                {
                    "employee_id": rec.employee_id.id,
                    "activity_type": "employee_reinitiate",
                    "date": rec.date,
                    "reinitiate_id": rec.id,
                    "description": rec.reason or "Employee Reinitiated",
                    "state": "approved",
                }
            )
            rec.activity_id = activity.id
        return records

    def _perform_final_approval(self):
        self.ensure_one()
        # Unarchive the employee and clear the departure details
        self.employee_id.write(
            {
                "active": True,
                "departure_date": False,
            }
        )
        # Post a message on their chatter
        self.employee_id.message_post(
            body=_("Employee successfully reinitiated and reactivated.")
        )
