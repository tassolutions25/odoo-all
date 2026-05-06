from odoo import models, fields, api

class HrLoanType(models.Model):
    _name = 'hr.loan.type'
    _description = 'Loan Type Configuration'

    name = fields.Char(string='Loan Type', required=True)
    interest_rate = fields.Float(string='Interest Rate (%)', default=0.0)
    eligibility_months_doj = fields.Integer(
        string='Eligibility (Months from DOJ)', 
        default=6,
        help="Minimum months of service required from Date of Joining."
    )
    salary_multiple_limit = fields.Integer(
        string='Salary Multiple Limit', 
        default=6,
        help="Maximum loan amount is basic salary multiplied by this value."
    )
    max_installment_months = fields.Integer(
        string='Max Installment Months', 
        default=36,
        help="Maximum allows months for repayment."
    )
    is_credit_committee_required = fields.Boolean(string='Credit Committee Approval Required', default=True)
    is_payroll_deduction = fields.Boolean(string='Is Payroll Deduction?', default=False, help="If checked, loans of this type will be deducted from payslips.")

    
    bank_account_type = fields.Selection([
        ('salary_advance', 'Salary Advance Account'),
        ('loan_settlement', 'Loan Settlement Account'),
        ('saving', 'Saving Account'),
        ('other', 'Other Account')
    ], string='Bank Account Type', default='loan_settlement', required=True)

    api_product_code = fields.Char(string='API Product Code', help="Match the 'loanProduct' field from the external API.")

    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Loan type name must be unique!')
    ]
