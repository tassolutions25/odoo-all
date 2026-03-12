# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class HrDocumentRequest(models.Model):
    _name = "hr.document.request"
    _description = "Employee Document Request"
    _order = "create_date desc"
    _inherit = ["hr.approval.mixin", "mail.thread", "mail.activity.mixin"]

    name = fields.Char(compute="_compute_name", store=True)
    employee_id = fields.Many2one(
        "hr.employee",
        string="Employee",
        required=True,
        default=lambda self: self.env.user.employee_id,
        readonly=True,
    )
    document_type = fields.Selection(
        [
            ("experience", "Experience Letter"),
            ("guarantee", "Guarantee Letter"),
            ("permanency", "Permanency Letter"),
            ("id", "ID Card Request/Renewal"),
        ],
        string="Document Type",
        required=True,
    )

    reason = fields.Text(string="Reason for Request", required=True)
    document_file = fields.Binary(string="Request Letter/Attachment", attachment=True)
    document_filename = fields.Char(string="Filename")

    activity_id = fields.Many2one(
        "hr.employee.activity",
        string="Activity Record",
        ondelete="set null",
        readonly=True,
    )

    @api.depends("employee_id", "document_type")
    def _compute_name(self):
        for rec in self:
            doc_type_display = dict(self._fields["document_type"].selection).get(
                rec.document_type
            )
            rec.name = (
                _("%s for %s") % (doc_type_display, rec.employee_id.name)
                if rec.employee_id
                else _("New Document Request")
            )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            activity = self.env["hr.employee.activity"].create(
                {
                    "employee_id": rec.employee_id.id,
                    "activity_type": "document_request",
                    "date": fields.Date.today(),
                    "document_request_id": rec.id,
                    "description": _("Request for %s") % rec.name,
                    "state": "draft",
                }
            )
            rec.activity_id = activity.id
        return records

    def _get_employee_for_approval(self):
        return self.employee_id

    def _perform_final_approval(self):
        self.ensure_one()
        self.message_post(
            body=_("Your document request has been approved. HR will now process it.")
        )
