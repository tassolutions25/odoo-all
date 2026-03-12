from odoo import models, fields, api


class HrApprovalLine(models.Model):
    _name = "hr.approval.line"
    _description = "HR Process Approval Line"
    _order = "sequence"

    sequence = fields.Integer(string="Sequence", default=10)
    approver_id = fields.Many2one("hr.employee", string="Approver", required=True)
    status = fields.Selection(
        [
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        string="Status",
        default="pending",
        required=True,
    )
    approval_date = fields.Datetime(string="Date", readonly=True)
    comments = fields.Text(string="Comments")

    res_model = fields.Char("Related Document Model", readonly=True, index=True)
    res_id = fields.Integer("Related Document ID", readonly=True, index=True)
