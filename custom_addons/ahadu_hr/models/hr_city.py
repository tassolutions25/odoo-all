from odoo import models, fields, api

class HrCity(models.Model):
    _name = "hr.city"
    _description = "City"
    _order = "name"

    name = fields.Char(string="City Name", required=True)
    region_id = fields.Many2one("hr.region", string="Region", required=True, ondelete="cascade")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    _sql_constraints = [
        ("name_region_uniq", "unique(name, region_id, company_id)", "The City Name must be unique per region and company."),
    ]
