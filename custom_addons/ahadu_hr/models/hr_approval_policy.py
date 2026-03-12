from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HrApprovalPolicy(models.Model):
    _name = "hr.approval.policy"
    _description = "HR Approval Workflow Policy"
    _order = "sequence, id"

    name = fields.Char(string="Policy Name", required=True)
    model_id = fields.Many2one(
        "ir.model",
        string="Applies to Model",
        required=True,
        domain=[("model", "ilike", "hr.employee.")],
        ondelete="cascade",
    )
    model_name = fields.Char(
        string="Model Name",
        related="model_id.model",
        store=True,
        readonly=True,
    )
    domain = fields.Char(
        string="Domain",
        default="[]",
        required=True,
        help="Domain to filter records this policy applies to. Use 'record' to refer to the document being approved.",
    )
    line_ids = fields.One2many(
        "hr.approval.policy.line", "policy_id", string="Approval Steps"
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text(string="Description")

    _sql_constraints = [
        ("name_uniq", "unique(name)", "The Policy Name must be unique."),
    ]


class HrApprovalPolicyLine(models.Model):
    _name = "hr.approval.policy.line"
    _description = "HR Approval Workflow Policy Line"
    _order = "sequence, id"

    policy_id = fields.Many2one(
        "hr.approval.policy", string="Policy", required=True, ondelete="cascade"
    )
    sequence = fields.Integer(
        default=10, help="Steps with the same sequence will be parallel."
    )
    approver_type = fields.Selection(
        [
            ("managerial_chain", "Managerial Hierarchy"),
            ("job_position", "Specific Job Position"),
        ],
        string="Approver Type",
        required=True,
        default="job_position",
    )
    job_id = fields.Many2one(
        "hr.job",
        string="Job Position",
        help="The employee holding this job position will be the approver.",
    )
    is_required = fields.Boolean(
        string="Is Required",
        default=True,
        help="If checked, an error will be raised if no approver can be found for this step.",
    )

    @api.constrains("approver_type", "job_id")
    def _check_approver_details(self):
        for line in self:
            if line.approver_type == "job_position" and not line.job_id:
                raise ValidationError(
                    _(
                        "You must specify a Job Position for the 'Specific Job Position' approver type."
                    )
                )
