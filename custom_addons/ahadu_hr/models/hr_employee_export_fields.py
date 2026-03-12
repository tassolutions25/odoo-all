# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class HrEmployeeInherit(models.Model):
    """Inherit hr.employee to add computed fields for bank accounts"""
    _inherit = 'hr.employee'

    bank_cash_indemnity = fields.Char(
        string='Bank Account - Cash Indemnity',
        compute='_compute_bank_accounts',
        store=True,
        help='Cash Indemnity Account Number'
    )
    bank_salary = fields.Char(
        string='Bank Account - Salary',
        compute='_compute_bank_accounts',
        store=True,
        help='Salary Account Number'
    )
    bank_salary_advance = fields.Char(
        string='Bank Account - Salary Advanced',
        compute='_compute_bank_accounts',
        store=True,
        help='Salary Advanced Account Number'
    )
    bank_saving = fields.Char(
        string='Bank Account - Saving',
        compute='_compute_bank_accounts',
        store=True,
        help='Saving Account Number'
    )
    bank_loan_settlement = fields.Char(
        string='Bank Account - Loan Settlement',
        compute='_compute_bank_accounts',
        store=True,
        help='Staff Loan Settlement Account Number'
    )
    bank_other = fields.Char(
        string='Bank Account - Other',
        compute='_compute_bank_accounts',
        store=True,
        help='Other Account Number'
    )

    # Add formatted date fields
    birthday_formatted = fields.Char(
        string='Birthday (DD/MM/YYYY)',
        compute='_compute_formatted_dates',
        store=True
    )
    date_of_joining_formatted = fields.Char(
        string='Date of Join (DD/MM/YYYY)',
        compute='_compute_formatted_dates',
        store=True
    )
    passport_expiry_date_formatted = fields.Char(
        string='Passport Expiry Date (DD/MM/YYYY)',
        compute='_compute_formatted_dates',
        store=True
    )
    passport_issue_date_formatted = fields.Char(
        string='Passport Issue Date (DD/MM/YYYY)',
        compute='_compute_formatted_dates',
        store=True
    )
    create_date_formatted = fields.Char(
        string='Created On (DD/MM/YYYY)',
        compute='_compute_formatted_dates',
        store=True
    )
    write_date_formatted = fields.Char(
        string='Last Updated On (DD/MM/YYYY)',
        compute='_compute_formatted_dates',
        store=True
    )
    first_contract_date = fields.Date(
        string='First Contract Date',
        compute='_compute_first_contract_date',
        store=True
    )
    first_contract_date_formatted = fields.Char(
        string='First Contract Date (DD/MM/YYYY)',
        compute='_compute_formatted_dates',
        store=True
    )

    bank_accounts_summary = fields.Text(
        string='Bank Accounts Summary',
        compute='_compute_flattened_summaries',
        store=True,
        help="List of all bank accounts in one cell"
    )
    education_history_summary = fields.Text(
        string='Education History Summary',
        compute='_compute_flattened_summaries',
        store=True,
        help="List of all education records in one cell"
    )
    deductions_summary = fields.Text(
        string='Deductions Summary',
        compute='_compute_flattened_summaries',
        store=False,
        help="List of all deductions in one cell"
    )
    
    @api.depends('bank_account_ids', 'bank_account_ids.account_type', 'bank_account_ids.account_number')
    def _compute_bank_accounts(self):
        """Compute bank account fields by type - Keeping legacy fields for backward compatibility"""
        for employee in self:
            # Initialize all fields
            employee.bank_cash_indemnity = ''
            employee.bank_salary = ''
            employee.bank_salary_advance = ''
            employee.bank_saving = ''
            employee.bank_loan_settlement = ''
            employee.bank_other = ''

            # Get first account of each type
            for account in employee.bank_account_ids:
                if account.account_type == 'cash_indemnity' and not employee.bank_cash_indemnity:
                    employee.bank_cash_indemnity = account.account_number
                elif account.account_type == 'salary' and not employee.bank_salary:
                    employee.bank_salary = account.account_number
                elif account.account_type == 'salary_advance' and not employee.bank_salary_advance:
                    employee.bank_salary_advance = account.account_number
                elif account.account_type == 'saving' and not employee.bank_saving:
                    employee.bank_saving = account.account_number
                elif account.account_type == 'loan_settlement' and not employee.bank_loan_settlement:
                    employee.bank_loan_settlement = account.account_number
                elif account.account_type == 'other' and not employee.bank_other:
                    employee.bank_other = account.account_number

    @api.depends('birthday', 'date_of_joining', 'passport_expiry_date', 'passport_issue_date', 'create_date', 'write_date', 'first_contract_date')
    def _compute_formatted_dates(self):
        """Compute formatted date fields in DD/MM/YYYY format"""
        for employee in self:
            employee.birthday_formatted = employee.birthday.strftime('%d/%m/%Y') if employee.birthday else ''
            employee.date_of_joining_formatted = employee.date_of_joining.strftime('%d/%m/%Y') if employee.date_of_joining else ''
            employee.passport_expiry_date_formatted = employee.passport_expiry_date.strftime('%d/%m/%Y') if employee.passport_expiry_date else ''
            employee.passport_issue_date_formatted = employee.passport_issue_date.strftime('%d/%m/%Y') if employee.passport_issue_date else ''
            employee.create_date_formatted = employee.create_date.strftime('%d/%m/%Y') if employee.create_date else ''
            employee.write_date_formatted = employee.write_date.strftime('%d/%m/%Y') if employee.write_date else ''
            employee.first_contract_date_formatted = employee.first_contract_date.strftime('%d/%m/%Y') if employee.first_contract_date else ''

    def _compute_first_contract_date(self):
        """Find the start date of the first contract"""
        for employee in self:
            contract = self.env['hr.contract'].search([
                ('employee_id', '=', employee.id)
            ], order='date_start asc', limit=1)
            employee.first_contract_date = contract.date_start if contract else False

    @api.depends('bank_account_ids', 'education_ids')
    def _compute_flattened_summaries(self):
        """Compute flattened summaries for One2Many fields"""
        for employee in self:
            # Bank Accounts
            bank_lines = []
            for acc in employee.bank_account_ids:
                bank_lines.append(f"{dict(acc._fields['account_type'].selection).get(acc.account_type, acc.account_type)}: {acc.account_number}")
            employee.bank_accounts_summary = "\n".join(bank_lines)

            # Education
            edu_lines = []
            for edu in employee.education_ids:
                start = edu.start_date.strftime('%d/%m/%Y') if edu.start_date else 'N/A'
                end = edu.end_date.strftime('%d/%m/%Y') if edu.end_date else 'N/A'
                edu_lines.append(f"{edu.school} ({edu.type_of_institution}) [{start} - {end}]")
            employee.education_history_summary = "\n".join(edu_lines)

            # Deductions
            ded_lines = []
            # deduction_ids comes from ahadu_payroll
            if hasattr(employee, 'deduction_ids'):
                for ded in employee.deduction_ids:
                    ded_lines.append(f"{ded.deduction_type}: {ded.monthly_amount} (Status: {ded.state})")
            employee.deductions_summary = "\n".join(ded_lines)


class HrEmployeeEducationInherit(models.Model):
    """Inherit hr.employee.education to add formatted date fields"""
    _inherit = 'hr.employee.education'

    start_date_formatted = fields.Char(
        string='Start Date (DD/MM/YYYY)',
        compute='_compute_formatted_dates',
        store=True
    )
    end_date_formatted = fields.Char(
        string='Graduation Date (DD/MM/YYYY)',
        compute='_compute_formatted_dates',
        store=True
    )

    @api.depends('start_date', 'end_date')
    def _compute_formatted_dates(self):
        """Compute formatted date fields in DD/MM/YYYY format"""
        for education in self:
            education.start_date_formatted = education.start_date.strftime('%d/%m/%Y') if education.start_date else ''
            education.end_date_formatted = education.end_date.strftime('%d/%m/%Y') if education.end_date else ''


class HrContractInherit(models.Model):
    """Inherit hr.contract to add formatted date fields"""
    _inherit = 'hr.contract'

    date_start_formatted = fields.Char(
        string='Start Date (DD/MM/YYYY)',
        compute='_compute_formatted_dates',
        store=True
    )
    date_end_formatted = fields.Char(
        string='End Date (DD/MM/YYYY)',
        compute='_compute_formatted_dates',
        store=True
    )

    @api.depends('date_start', 'date_end')
    def _compute_formatted_dates(self):
        """Compute formatted date fields for contract"""
        for contract in self:
            contract.date_start_formatted = contract.date_start.strftime('%d/%m/%Y') if contract.date_start else ''
            contract.date_end_formatted = contract.date_end.strftime('%d/%m/%Y') if contract.date_end else ''


class HrDistrictInherit(models.Model):
    """Inherit hr.district to add formatted date fields"""
    _inherit = 'hr.district'

    write_date_formatted = fields.Char(
        string='Last Updated On (DD/MM/YYYY)',
        compute='_compute_formatted_dates',
        store=True
    )

    @api.depends('write_date')
    def _compute_formatted_dates(self):
        """Compute formatted date fields for district"""
        for district in self:
            district.write_date_formatted = district.write_date.strftime('%d/%m/%Y') if district.write_date else ''
