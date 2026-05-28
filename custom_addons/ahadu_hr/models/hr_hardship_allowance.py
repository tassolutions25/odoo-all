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
    city_ids = fields.One2many(
        "hr.city",
        "hardship_allowance_level_id",
        string="Cities",
    )

    _sql_constraints = [
        ("name_uniq", "unique(name)", "The Level Name must be unique."),
    ]

    def unlink(self):
        cities = self.mapped("city_ids")
        if cities:
            employees = (
                self.env["hr.employee"].sudo().search([("city_id", "in", cities.ids)])
            )
            if employees:
                employees.write({"hardship_allowance_level_id": False})
        return super().unlink()
