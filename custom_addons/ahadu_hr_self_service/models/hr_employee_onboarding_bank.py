from odoo import models, fields

class HrEmployeeOnboardingBankAccount(models.Model):
    _name = "hr.employee.onboarding.bank.account"
    _description = "Employee Onboarding Bank Account"
    _order = "id"

    onboarding_id = fields.Many2one(
        "hr.employee.onboarding",
        string="Onboarding Request",
        ondelete="cascade",
        required=True,
    )
    bank_id = fields.Many2one("res.bank", string="Bank Name", required=True)
    bank_country_id = fields.Many2one("res.country", string="Bank Country", required=True)
    account_number = fields.Char(string="Account Number", required=True)
    currency_id = fields.Many2one("res.currency", string="Currency")
    account_holder_name = fields.Char(string="Account Holder Name")
    account_type = fields.Selection(
        [
            ("cash_indemnity", "Cash Indemnity Account"),
            ("salary", "Salary Account"),
            ("salary_advance", "Salary Advanced Account"),
            ("saving", "Saving Account"),
            ("loan_settlement", "Staff Loan Settlement Account"),
            ("other", "Other"),
        ],
        string="Account Type",
        required=True,
    )