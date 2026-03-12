from odoo import models, fields, api, _


class HrEmployeeConfirmation(models.Model):
    _name = "hr.employee.confirmation"
    _description = "Employee Probation Confirmation"
    _inherit = ["mail.thread", "mail.activity.mixin", "hr.approval.mixin"]
    _order = "date desc"

    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)
    date = fields.Date(
        string="Confirmation Date", default=fields.Date.today, required=True
    )
    reason = fields.Text(string="Notes")
    activity_id = fields.Many2one("hr.employee.activity", string="Activity Record")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            activity = self.env["hr.employee.activity"].create(
                {
                    "employee_id": rec.employee_id.id,
                    "activity_type": "confirmation",
                    "date": rec.date,
                    "confirmation_id": rec.id,
                    "description": "Employee Confirmed (Probation Ended)",
                    "state": "approved",
                }
            )
            rec.activity_id = activity.id
        return records

    def _perform_final_approval(self):
        # Logic to clear probation fields on employee
        pass
