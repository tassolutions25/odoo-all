from odoo import models, fields

class AhaduAccount(models.Model):
    _name = 'ahadu.account'
    _description = 'Payroll Account'
    _order = 'code'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Account Code', required=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'The Account Code must be unique!')
    ]