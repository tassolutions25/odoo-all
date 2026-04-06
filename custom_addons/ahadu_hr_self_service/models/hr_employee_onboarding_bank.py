from odoo import models, fields, api
from odoo.exceptions import ValidationError


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
    bank_country_id = fields.Many2one(
        "res.country", string="Bank Country", required=True
    )
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

    @api.constrains("account_number")
    def _check_account_number_length(self):
        for rec in self:
            if rec.account_number and (
                not rec.account_number.isdigit() or len(rec.account_number) != 13
            ):
                raise ValidationError(
                    _("Bank Account Number must be exactly 13 digits.")
                )

    @api.model
    def default_get(self, fields):
        res = super(HrEmployeeOnboardingBankAccount, self).default_get(fields)
        bank = self.env["res.bank"].search([("name", "ilike", "Ahadu")], limit=1)
        if bank:
            res["bank_id"] = bank.id
        return res
