# models/hr_employee_bank.py

from odoo import models, fields, api


class HrEmployeeBankAccount(models.Model):
    _name = "hr.employee.bank.account"
    _description = "Employee Bank Details"

    employee_id = fields.Many2one(
        "hr.employee", string="Employee", required=True, ondelete="cascade"
    )

    balance = fields.Monetary(
        string="Balance", 
        currency_field="currency_id",
        help="Current balance for Cash Indemnity accounts."
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

    # Prevent duplicate account numbers
    _sql_constraints = [
        (
            "account_number_uniq",
            "unique(account_number)",
            "The bank account number must be unique!",
        )
    ]
