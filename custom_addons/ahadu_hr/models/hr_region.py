from odoo import models, fields

class HrRegion(models.Model):
    _name = "hr.region"
    _description = "Region"
    _order = "name"

    name = fields.Char(string="Region Name", required=True)
    code = fields.Char(string="Code", help="Legacy Region Code")
    description = fields.Text(string="Description")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    city_ids = fields.One2many("hr.city", "region_id", string="Cities")

    _sql_constraints = [
        ("name_uniq", "unique(name, company_id)", "The Region Name must be unique per company."),
    ]