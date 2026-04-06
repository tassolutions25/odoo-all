from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HrEmployeeBankAccount(models.Model):
    _name = "hr.employee.bank.account"
    _description = "Employee Bank Details"

    employee_id = fields.Many2one(
        "hr.employee", string="Employee", required=True, ondelete="cascade"
    )

    balance = fields.Monetary(
        string="Balance",
        currency_field="currency_id",
        help="Current balance for Cash Indemnity accounts.",
    )

    bank_id = fields.Many2one(
        "res.bank",
        string="Bank",
        default=lambda self: self.env.ref(
            "ahadu_hr.res_bank_ahadu", raise_if_not_found=False
        ),
    )

    bank_country_id = fields.Many2one(
        "res.country",
        string="Bank Country",
        default=lambda self: self.env.ref("base.et", raise_if_not_found=False),
    )

    account_number = fields.Char(string="Account Number", required=True)

    account_holder_name = fields.Char(
        string="Account Holder Name",
        help="The name of the person/entity holding the account.",
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
    )

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
        res = super(HrEmployeeBankAccount, self).default_get(fields)
        bank = self.env["res.bank"].search([("name", "ilike", "Ahadu")], limit=1)
        if bank:
            res["bank_id"] = bank.id
        return res

    # Prevent duplicate account numbers
    _sql_constraints = [
        (
            "account_number_uniq",
            "unique(account_number)",
            "The bank account number must be unique!",
        )
    ]
