from odoo import models, fields, api

class AhaduPayrollCampaign(models.Model):
    _name = 'ahadu.payroll.campaign'
    _description = 'Payroll Deduction Campaign'
    _order = 'name'

    name = fields.Char(string='Campaign Name', required=True)
    code = fields.Char(string='Campaign Code')
    credit_account_id = fields.Many2one('ahadu.account', string='Credit Account (Ahadu)', required=True, help="The GL account to credit for this campaign.")
    active = fields.Boolean(string='Active', default=True)
    description = fields.Text(string='Description')

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'The Campaign Code must be unique!')
    ]
