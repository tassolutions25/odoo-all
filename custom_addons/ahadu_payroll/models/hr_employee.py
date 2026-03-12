from odoo import models, fields, api

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # ====================
    # SIMPLE PAYROLL FIELDS
    # ====================
    
    # Current Salary from Contract
    current_salary = fields.Monetary(
        string='Current Basic Salary',
        compute='_compute_current_salary',
        currency_field='currency_id',
        help="Current basic salary from active contract"
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )

    # Payslip Count
    payslip_count = fields.Integer(
        string='Total Payslips',
        compute='_compute_payslip_count'
    )
    
    # Deduction Count
    deduction_count = fields.Integer(
        string='Active Deductions',
        compute='_compute_deduction_count'
    )
    
    # Deductions - One2many for tab view
    deduction_ids = fields.One2many(
        'hr.employee.deduction',
        'employee_id',
        string='Deductions'
    )
    
    # Loans - One2many for tab view
    loan_ids = fields.One2many(
        'hr.loan',
        'employee_id',
        string='Loans'
    )
    
    @api.depends('emp_wage')
    def _compute_current_salary(self):
        """Get current salary from employee wage field (from ahadu.hr module)."""
        for employee in self:
            # Use emp_wage from custom ahadu.hr module
            if hasattr(employee, 'emp_wage'):
                employee.current_salary = employee.emp_wage or 0.0
            else:
                employee.current_salary = 0.0
    
    def _compute_payslip_count(self):
        """Count payslips for this employee."""
        for employee in self:
            employee.payslip_count = self.env['hr.payslip'].search_count([
                ('employee_id', '=', employee.id)
            ])
    
    def _compute_deduction_count(self):
        """Count active deductions for this employee."""
        for employee in self:
            employee.deduction_count = self.env['hr.employee.deduction'].search_count([
                ('employee_id', '=', employee.id),
                ('state', '=', 'active')
            ])
    
    def action_view_payslips(self):
        """Action to view all payslips for this employee."""
        self.ensure_one()
        return {
            'name': 'My Payslips',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip',
            'view_mode': 'tree,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }