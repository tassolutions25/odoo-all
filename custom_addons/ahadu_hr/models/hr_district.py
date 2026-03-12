from odoo import models, fields


class HrDistrict(models.Model):
    _name = "hr.district"
    _description = "District"
    _order = "name"

    name = fields.Char(string="District Name", required=True)
    code = fields.Char(string="District Code", size=10)
    active = fields.Boolean(string="Active", default=True)

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    _sql_constraints = [
        (
            "name_uniq",
            "unique(name, company_id)",
            "The District Name must be unique per company.",
        ),
        (
            "code_uniq",
            "unique(code, company_id)",
            "The District Code must be unique per company.",
        ),
    ]
