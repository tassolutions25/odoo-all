from odoo import models, fields, api, _


class HrEmployeeDisciplinary(models.Model):
    _name = "hr.employee.disciplinary"
    _description = "Employee Disciplinary Action"
    _order = "action_date desc"
    _inherit = ["mail.thread", "mail.activity.mixin", "hr.approval.mixin"]

    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)
    action_date = fields.Date(
        string="Action Date", required=True, default=fields.Date.today
    )
    action_type = fields.Selection(
        [
            ("warning", "Warning"),
            ("suspension", "Suspension"),
            ("fine", "Fine"),
        ],
        string="Action Type",
        required=True,
    )
    violation = fields.Text(string="Violation Description", required=True)
    action_taken = fields.Text(string="Action Taken", required=True)
    duration = fields.Integer(string="Duration (Days)", help="For suspension actions")
    activity_id = fields.Many2one(
        "hr.employee.activity", string="Activity Record", ondelete="set null"
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            activity = self.env["hr.employee.activity"].create(
                {
                    "employee_id": rec.employee_id.id,
                    "activity_type": "disciplinary",
                    "date": rec.action_date,
                    "disciplinary_id": rec.id,
                    "description": f"Disciplinary Action - {dict(self._fields['action_type'].selection).get(rec.action_type)}",
                }
            )
            rec.activity_id = activity.id
        return records

    def _perform_final_approval(self):
        """
        Logic to execute upon final approval.
        For a disciplinary action, the main outcome is that the record is
        officially approved. No further state change or employee update
        is automatically performed.
        """
        self.ensure_one()
        # The state is automatically set to 'approved' by the mixin.
        if self.activity_id:
            self.activity_id.action_approve()
