from odoo import models, fields


class HrGrade(models.Model):
    _name = "hr.grade"
    _description = "Employee Grade"
    _order = "name"

    name = fields.Integer(string="Grade", required=True)
    description = fields.Text(string="Description")
    active = fields.Boolean(string="Active", default=True)

    _sql_constraints = [
        ("name_unique", "unique(name)", "Grade name must be unique!"),
    ]
