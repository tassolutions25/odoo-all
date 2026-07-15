from odoo import models, fields

class RiskCategory(models.Model):
    _name = 'risk.category'
    _description = 'Risk Category Configuration'
    _order = 'sequence, id'

    name = fields.Char('Category Name', required=True, translate=True)
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)
    description = fields.Text('Description')
