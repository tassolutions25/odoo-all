from odoo import models, fields, api


class HrHardshipAllowanceLevel(models.Model):
    _name = "hr.hardship.allowance.level"
    _description = "Hardship Allowance Level"
    _order = "sequence"

    name = fields.Char(
        string="Level Name", required=True, help="e.g., High, Medium, Low"
    )
    sequence = fields.Integer(default=10)
    value_percentage = fields.Float(string="Percentage (%)", required=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("name_uniq", "unique(name)", "The Level Name must be unique."),
    ]
