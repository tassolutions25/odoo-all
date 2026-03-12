# from odoo import models, fields, api


# class ahadu_theme(models.Model):
#     _name = 'ahadu_theme.ahadu_theme'
#     _description = 'ahadu_theme.ahadu_theme'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

