from odoo import models, fields


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    onboarding_ids = fields.One2many(
        "hr.employee.onboarding", "employee_id", string="Onboarding Requests"
    )
    document_request_ids = fields.One2many(
        "hr.document.request", "employee_id", string="Document Requests"
    )
