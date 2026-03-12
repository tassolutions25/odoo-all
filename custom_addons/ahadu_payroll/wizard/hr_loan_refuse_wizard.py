from odoo import models, fields, api

class HrLoanRefuseWizard(models.TransientModel):
    _name = 'hr.loan.refuse.wizard'
    _description = 'Loan Refusal Wizard'

    loan_id = fields.Many2one('hr.loan', string='Loan', required=True)
    reason = fields.Text(string='Reason', required=True)

    def action_refuse(self):
        self.loan_id.write({
            'state': 'refused',
            'refusal_reason': self.reason
        })
        self.loan_id.message_post(body=f"Loan Refused. Reason: {self.reason}")
