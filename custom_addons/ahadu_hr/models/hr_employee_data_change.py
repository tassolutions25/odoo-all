from odoo import models, fields, api, _


class HrEmployeeDataChange(models.Model):
    _name = "hr.employee.data.change"
    _description = "Employee Data/Profile Change"
    _inherit = ["mail.thread", "mail.activity.mixin", "hr.approval.mixin"]
    _order = "date desc"

    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)
    date = fields.Date(
        string="Effective Date", default=fields.Date.today, required=True
    )

    change_summary = fields.Text(string="Change Summary", required=True)

    activity_id = fields.Many2one(
        "hr.employee.activity", string="Activity Record", ondelete="cascade"
    )

    def _compute_name(self):
        for rec in self:
            rec.name = f"Data Change - {rec.employee_id.name}"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            activity = self.env["hr.employee.activity"].create(
                {
                    "employee_id": rec.employee_id.id,
                    "activity_type": "data_change",
                    "date": rec.date,
                    "data_change_id": rec.id,  # We will link this field in Step 2
                    "description": rec.change_summary,
                    "state": "approved",  # Migration data is usually auto-approved
                }
            )
            rec.activity_id = activity.id
        return records

    def _perform_final_approval(self):
        # Data changes are usually applied immediately or via the migration script logic.
        # This method is required by the mixin.
        pass
