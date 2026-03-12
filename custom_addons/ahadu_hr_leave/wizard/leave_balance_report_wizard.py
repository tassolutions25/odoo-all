from odoo import models, fields, api, _

class LeaveBalanceReportWizard(models.TransientModel):
    _name = 'ahadu.leave.balance.report.wizard'
    _description = 'Leave Balance by Accrual Year Report Wizard'

    employee_id = fields.Many2one(
        'hr.employee', string="Employee", required=True,
        default=lambda self: self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
    )

    def action_print_report(self):
        """
        [DEFINITIVE FIX] This method now performs all calculations and "pushes"
        the data directly into the report's CONTEXT.
        """
        self.ensure_one()
        
        allocations = self.env['hr.leave.allocation'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'validate'),
        ], order='date_from asc')

        balances_by_year = {}
        for alloc in allocations:
            if not alloc.date_from:
                continue
            
            year = alloc.date_from.year
            if year not in balances_by_year:
                balances_by_year[year] = {
                    'year': year, 'granted': 0.0, 'used': 0.0,
                    'expired': 0.0, 'balance': 0.0,
                }
            
            balances_by_year[year]['granted'] += alloc.number_of_days
            balances_by_year[year]['used'] += alloc.leaves_taken
            balances_by_year[year]['expired'] += alloc.expired_leaves
            balances_by_year[year]['balance'] += alloc.effective_remaining_leaves

        report_lines = sorted(balances_by_year.values(), key=lambda x: x['year'])
        total_granted = sum(line['granted'] for line in report_lines)
        total_used = sum(line['used'] for line in report_lines)
        total_expired = sum(line['expired'] for line in report_lines)
        total_balance = sum(line['balance'] for line in report_lines)

        # Prepare the dictionary of data we want to send.
        report_data = {
            'lines': report_lines,
            'total_granted': total_granted,
            'total_used': total_used,
            'total_expired': total_expired,
            'total_balance': total_balance,
        }
        
        # Get the report action.
        report = self.env.ref('ahadu_hr_leave.action_report_leave_balance_by_year')
        
        # Use .with_context() to inject our data dictionary into the report's context.
        # Then, call the report action.
        return report.with_context(report_data=report_data).report_action(self)