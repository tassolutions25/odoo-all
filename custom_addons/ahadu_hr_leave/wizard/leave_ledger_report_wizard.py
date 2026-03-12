from odoo import models, fields, api, _
from odoo.exceptions import UserError

class LeaveLedgerReportWizard(models.TransientModel):
    _name = 'ahadu.leave.ledger.wizard'
    _description = 'Leave Ledger Report Wizard'

    employee_id = fields.Many2one(
        'hr.employee', string="Employee", required=True,
        default=lambda self: self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
    )
    date_from = fields.Date(string="Start Date", required=True)
    date_to = fields.Date(string="End Date", required=True)

    def _get_report_data(self):
        """
        [NEW ROBUST METHOD] This method is called directly from the QWeb template.
        It performs all calculations and returns one complete dictionary.
        """
        self.ensure_one()
        annual_leave_type = self.env.ref('ahadu_hr_leave.ahadu_leave_type_annual', raise_if_not_found=False)
        if not annual_leave_type:
            raise UserError(_("The 'Annual Leave' Leave Type could not be found."))
        
        # --- Opening Balance Calculation ---
        opening_allocs = self.env['hr.leave.allocation'].search([
            ('employee_id', '=', self.employee_id.id), ('holiday_status_id', '=', annual_leave_type.id),
            ('date_from', '<', self.date_from), ('state', '=', 'validate'),
        ])
        leaves_before = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_id.id), ('holiday_status_id', '=', annual_leave_type.id),
            ('request_date_from', '<', self.date_from), ('state', '=', 'validate'),
        ])
        opening_balance = sum(opening_allocs.mapped('number_of_days')) - sum(leaves_before.mapped('number_of_days'))

        # --- Transaction Calculation ---
        transactions = []
        allocs_in_period = self.env['hr.leave.allocation'].search([
            ('employee_id', '=', self.employee_id.id), ('holiday_status_id', '=', annual_leave_type.id),
            ('date_from', '>=', self.date_from), ('date_from', '<=', self.date_to),
        ], order='date_from asc')
        for alloc in allocs_in_period:
            transactions.append({'date': alloc.date_from, 'type': 'Accrual', 'details': f"Annual Allocation for {alloc.date_from.year}", 'debit': alloc.number_of_days, 'credit': 0})
            if alloc.expired_leaves > 0 and alloc.expiry_date and self.date_from <= alloc.expiry_date <= self.date_to:
                transactions.append({'date': alloc.expiry_date, 'type': 'Expiry', 'details': f"Expired from {alloc.date_from.year}", 'debit': 0, 'credit': alloc.expired_leaves})

        leaves_in_period = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_id.id), ('holiday_status_id', '=', annual_leave_type.id),
            ('request_date_from', '>=', self.date_from), ('request_date_from', '<=', self.date_to),
            ('state', '=', 'validate'),
        ], order='request_date_from asc')
        for leave in leaves_in_period:
            transactions.append({'date': leave.request_date_from, 'type': 'Leave Taken', 'details': leave.name or 'Annual Leave', 'debit': 0, 'credit': leave.number_of_days})
            
        # --- Final Processing ---
        sorted_transactions = sorted(transactions, key=lambda t: t['date'])
        running_balance = opening_balance
        for trans in sorted_transactions:
            running_balance += trans['debit'] - trans['credit']
            trans['balance'] = running_balance

        return {
            'opening_balance': opening_balance,
            'lines': sorted_transactions,
            'closing_balance': running_balance,
        }

    def action_print_report(self):
        self.ensure_one()
        return self.env.ref('ahadu_hr_leave.action_report_leave_ledger').report_action(self)
    