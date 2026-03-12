# -*- coding: utf-8 -*-
from odoo import models, fields


class HrEmployeeEducation(models.Model):
    _inherit = "hr.employee.education"

    onboarding_id = fields.Many2one(
        "hr.employee.onboarding", string="Onboarding Request", ondelete="cascade"
    )
