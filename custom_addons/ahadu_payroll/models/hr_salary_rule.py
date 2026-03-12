from odoo import models, fields

class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    # Link to our custom standalone accounts
    ahadu_debit_account_id = fields.Many2one('ahadu.account', string='Debit Account (Ahadu)')
    ahadu_credit_account_id = fields.Many2one('ahadu.account', string='Credit Account (Ahadu)')