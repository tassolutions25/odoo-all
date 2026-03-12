from odoo import models, fields, api, _


class HrEmployeeReinitiate(models.Model):
    _name = "hr.employee.reinitiate"
    _description = "Employee Reinitiate"
    _inherit = ["mail.thread", "mail.activity.mixin", "hr.approval.mixin"]
    _order = "date desc"

    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)
    date = fields.Date(string="Date", default=fields.Date.today, required=True)
    reason = fields.Text(string="Reason")
    activity_id = fields.Many2one("hr.employee.activity", string="Activity Record")

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
        pass
