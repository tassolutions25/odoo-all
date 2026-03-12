from odoo import models, fields


class HrCostCenter(models.Model):
    _name = "hr.cost.center"
    _description = "Cost Center"
    _order = "name"

    name = fields.Char(string="Cost Center Name", required=True, index=True)
    code = fields.Char(string="Cost Center Code", size=10)

    _sql_constraints = [
        ("name_uniq", "unique(name)", "The Cost Center name must be unique."),
    ]
