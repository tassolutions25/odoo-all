# -*- coding: utf-8 -*-
from odoo import models, fields


class HrEmployeeExperience(models.Model):
    _inherit = "hr.employee.experience"

    # Links experience lines with the onboarding request before approval
    onboarding_id = fields.Many2one(
        "hr.employee.onboarding", string="Onboarding Request", ondelete="cascade"
    )

    # Overrides and relaxes the required constraint so that these temporary
    # experience lines can be saved without a direct employee link until approved.
    employee_id = fields.Many2one(
        "hr.employee", string="Employee", required=False, ondelete="cascade"
    )
