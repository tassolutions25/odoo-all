from odoo import models, fields, api

class HrEmployeeDeduction(models.Model):
    _name = 'hr.employee.deduction'
    _description = 'Employee Loan/Savings Deduction'
    _order = 'employee_id, deduction_type, id'

    name = fields.Char(string='Reference', required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, ondelete='cascade')
    
    deduction_type = fields.Selection([
        ('savings', 'Savings'),
        ('credit_association', 'Credit Association'),
        ('cost_sharing', 'Cost Sharing'),
        ('penalty', 'Penalty Deduction'),
        ('other', 'Other Deduction')
    ], string='Type', required=True, default='other')
    
    # Loan-specific fields
    principal_amount = fields.Float(string='Principal Amount', help="Original loan amount")
    interest_rate = fields.Float(string='Interest Rate (%)', help="Annual interest rate")
    total_installments = fields.Integer(string='Total Installments', help="Total number of monthly payments")
    paid_installments = fields.Integer(string='Paid Installments', default=0, help="Number of installments already paid")
    
    # Penalty-specific fields
    penalty_percentage = fields.Float(
        string='Penalty %',
        help="Percentage of basic salary to deduct as penalty"
    )
    penalty_reason = fields.Text(string='Penalty Reason', help="Reason for the penalty deduction")
    
    # Common fields
    monthly_amount = fields.Float(string='Monthly Deduction', help="Fixed amount to deduct each month (for non-penalty types)")
    start_date = fields.Date(string='Start Date', default=fields.Date.context_today)
    end_date = fields.Date(string='End Date', help="Leave empty for ongoing deductions")
    
    remaining_balance = fields.Float(string='Remaining Balance', compute='_compute_remaining', store=True)
    
    state = fields.Selection([
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='active')
    
    notes = fields.Text(string='Notes')
    
    @api.depends('principal_amount', 'monthly_amount', 'paid_installments')
    def _compute_remaining(self):
        for record in self:
            record.remaining_balance = 0
    
    def action_complete(self):
        """Mark deduction as completed."""
        self.write({'state': 'completed'})
    
    def action_cancel(self):
        """Cancel the deduction."""
        self.write({'state': 'cancelled'})
    
    def action_reactivate(self):
        """Reactivate a cancelled deduction."""
        self.write({'state': 'active'})
    
    def increment_paid_installment(self):
        """Called after payslip is confirmed to track installments if needed."""
        pass
