from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HrEmployeeGuarantee(models.Model):
    _name = "hr.employee.guarantee"
    _description = "Employee Guarantee"
    _order = "guarantee_date desc"

    _inherit = ["mail.thread", "mail.activity.mixin", "hr.approval.mixin"]

    name = fields.Char(string="Reference", compute="_compute_name", store=True)
    employee_id = fields.Many2one(
        "hr.employee",
        string="Guarantor (Employee)",
        required=True,
        tracking=True,
        help="The employee from this company who is acting as the guarantor.",
        default=lambda self: self.env.user.employee_id,
    )

    guaranteed_person_name = fields.Char(
        string="Guaranteed Person's Name", required=True
    )
    guaranteed_person_company = fields.Char(
        string="Guaranteed Person's Company/Organization",
        required=True,
        tracking=True,
    )
    guaranteed_person_id_number = fields.Char(
        string="Guaranteed Person's ID Number", tracking=True
    )

    guarantee_date = fields.Date(
        string="Guarantee Date", required=True, default=fields.Date.today, tracking=True
    )
    # guarantee_type = fields.Selection(
    #     [
    #         ("employment", "Employment Guarantee"),
    #         ("financial", "Financial Guarantee"),
    #         ("performance", "Performance Guarantee"),
    #     ],
    #     string="Guarantee Type",
    #     required=True,
    # )

    amount = fields.Float(string="Guarantee Amount", tracking=True)
    description = fields.Text(string="Description", tracking=True)

    po_box = fields.Char(string="P.O. Box", tracking=True)
    organization_email = fields.Char(string="Organization Email", tracking=True)

    activity_id = fields.Many2one(
        "hr.employee.activity",
        string="Activity Record",
        ondelete="set null",
        readonly=True,
    )

    @api.depends("employee_id", "guaranteed_person_name")
    def _compute_name(self):
        for rec in self:
            if rec.employee_id and rec.guaranteed_person_name:
                rec.name = f"Guarantee by {rec.employee_id.name} for {rec.guaranteed_person_name}"
            else:
                rec.name = _("New Guarantee")

    def _get_employee_for_approval(self):
        """
        Required by the mixin. Returns the employee for whom the request is being made.
        In this case, it's the guarantor employee.
        """
        return self.employee_id

    def _perform_final_approval(self):
        """
        Required by the mixin. This logic runs after the final approval step.
        The mixin already sets the state to 'approved'.
        We can add any additional logic here, like posting a confirmation message.
        """
        self.ensure_one()
        self.message_post(body=_("The guarantee request has been fully approved."))

    @api.constrains("po_box", "organization_email")
    def _check_contact_info(self):
        for record in self:
            if not record.po_box and not record.organization_email:
                raise ValidationError(
                    "You must provide either a P.O. Box or an Organization Email for the guaranteed person's organization."
                )

    @api.constrains("employee_id", "state")
    def _check_guarantee_limit(self):
        for record in self:
            if record.employee_id and record.state == "approved":
                active_guarantees_count = self.search_count(
                    [
                        ("employee_id", "=", record.employee_id.id),
                        ("state", "=", "approved"),
                        ("id", "!=", record.id),
                    ]
                )
                if active_guarantees_count >= 2:
                    raise ValidationError(
                        _(
                            "Employee %s has already reached the maximum limit of 2 active guarantees.",
                            record.employee_id.name,
                        )
                    )

    @api.model_create_multi
    def create(self, vals_list):
        guarantees = super().create(vals_list)
        for guarantee in guarantees:
            activity_vals = {
                "employee_id": guarantee.employee_id.id,
                "activity_type": "guarantee",
                "date": guarantee.guarantee_date,
                "guarantee_id": guarantee.id,
                "description": f"Provided guarantee for {guarantee.guaranteed_person_name}",
            }
            activity = self.env["hr.employee.activity"].create(activity_vals)
            guarantee.activity_id = activity.id
        return guarantees
