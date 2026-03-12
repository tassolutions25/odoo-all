from odoo import models, fields

class PublicHoliday(models.Model):
    _name = 'ahadu.public.holiday'
    _description = 'Public Holiday'
    _order = 'date desc'

    name = fields.Char(string="Holiday Name", required=True)
    date = fields.Date(string="Date", required=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )