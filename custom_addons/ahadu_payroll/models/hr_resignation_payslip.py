# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class HrResignationPayslip(models.Model):
    _name = 'hr.resignation.payslip'
    _description = 'Resignation Payslip'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name', readonly=True, compute='_compute_name')
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, tracking=True)
    # Removing run_id for now as there's no resignation run model, or leaving it out if unused.
    # run_id = fields.Many2one('hr.resignation.run', string='Batch', ondelete='cascade', tracking=True)
    
    resignation_date = fields.Date(string='Resignation Date', required=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('calculated', 'Calculated'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ], string='Status', default='draft', tracking=True)

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    prepared_by_id = fields.Many2one(
        'res.users', 
        string='Prepared By', 
        readonly=True, 
        tracking=True
    )
    approved_by_id = fields.Many2one(
        'res.users', 
        string='Approved By', 
        readonly=True, 
        tracking=True
    )

    # --- Leave Pay Fields ---
    wage = fields.Monetary(string='Basic Salary')
    leave_days = fields.Float(string='Unutilized Annual Leave', digits=(16, 2))
    
    leave_pay_gross = fields.Monetary(string='Leave Pay (Gross)')
    leave_pay_tax = fields.Monetary(string='Tax Amount (Leave)')
    leave_pay_net = fields.Monetary(string='Leave Pay (Net)', compute='_compute_leave_pay_net')

    @api.depends('leave_pay_gross', 'leave_pay_tax')
    def _compute_leave_pay_net(self):
        for rec in self:
            rec.leave_pay_net = rec.leave_pay_gross - rec.leave_pay_tax

    # --- Unpaid Salary Fields ---
    present_days = fields.Integer(string='Present Days')
    unpaid_salary = fields.Monetary(string='Unpaid Salary')
    unpaid_transport = fields.Monetary(string='Unpaid Transport')
    unpaid_housing = fields.Monetary(string='Unpaid Housing')
    unpaid_mobile = fields.Monetary(string='Unpaid Mobile')
    representation_allowance = fields.Monetary(string='Representation')
    
    gross_amount = fields.Monetary(string='Gross Amount (Salary)')
    taxable_amount = fields.Monetary(string='Taxable Amount')
    tax_salary = fields.Monetary(string='Tax Amount (Salary)')
    
    # --- Deductions ---
    grand_tax = fields.Monetary(string='Total Tax', compute='_compute_grand_tax', store=True)
    pension_emp = fields.Monetary(string='Pension (7%)')
    pension_comp = fields.Monetary(string='Pension (11%)')
    
    # Manual Deductions
    lost_id_card = fields.Monetary(string='Lost ID Card')
    vat_on_id_card = fields.Monetary(string='VAT on ID Card')
    other_deductions = fields.Monetary(string='Other Deductions')
    
    total_deduction = fields.Monetary(string='Total Deduction')
    
    # --- Final Net ---
    net_payable = fields.Monetary(string='Net Resignation Payable')

    @api.depends('leave_pay_tax', 'tax_salary')
    def _compute_grand_tax(self):
        for rec in self:
            rec.grand_tax = rec.leave_pay_tax + rec.tax_salary

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            # Try to fetch resignation_date from hr.employee.resignation
            resignation = self.env['hr.employee.resignation'].search([
                ('employee_id', '=', self.employee_id.id),
                ('state', 'in', ['approved', 'Approved'])
            ], limit=1, order='resignation_date desc')
            
            if resignation and hasattr(resignation, 'resignation_date'):
                self.resignation_date = resignation.resignation_date
            elif self.employee_id.contract_id.date_end:
                self.resignation_date = self.employee_id.contract_id.date_end
            else:
                self.resignation_date = False
                return {
                    'warning': {
                        'title': _("Warning"),
                        'message': _("No approved resignation record or Contract End Date found for this employee.")
                    }
                }

    def _check_officer_only(self):
        """Check if user is a Manager (blocked from Officer tasks)."""
        if self.env.user.has_group('payroll.group_payroll_manager') and not self.env.user.has_group('base.group_system'):
            from odoo.exceptions import AccessError
            raise AccessError(_("Payroll Managers are restricted from this action (Create/Compute). This action is reserved for Payroll Officers."))

    def _check_manager_only(self):
        """Check if user is NOT a Manager (blocked from Manager tasks)."""
        if not self.env.user.has_group('payroll.group_payroll_manager') and not self.env.user.has_group('base.group_system'):
            from odoo.exceptions import AccessError
            raise AccessError(_("Only Payroll Managers can perform this action (Approve)."))

    @api.model
    def create(self, vals):
        self._check_officer_only()
        if 'employee_id' in vals and not vals.get('resignation_date'):
            employee = self.env['hr.employee'].browse(vals['employee_id'])
            resignation = self.env['hr.employee.resignation'].search([
                ('employee_id', '=', employee.id),
                ('state', 'in', ['approved', 'Approved'])
            ], limit=1, order='resignation_date desc')
            
            if resignation and hasattr(resignation, 'resignation_date'):
                vals['resignation_date'] = resignation.resignation_date
            elif employee.contract_id.date_end:
                vals['resignation_date'] = employee.contract_id.date_end
            else:
                from odoo.exceptions import UserError
                raise UserError(_("Please provide a Resignation Date."))
            
        return super(HrResignationPayslip, self).create(vals)

    def _compute_name(self):
        for rec in self:
            rec.name = f"Resignation Pay - {rec.employee_id.name}"

    def compute_sheet(self):
        for rec in self:
            rec._check_officer_only()
            rec.prepared_by_id = self.env.user.id
            rec._compute_values()
            rec.state = 'calculated'

    def _compute_values(self):
        """
        Main calculation logic for Resignation Pay.
        """
        self.ensure_one()
        
        if not self.employee_id or not self.resignation_date:
            return

        self.wage = self.employee_id.emp_wage or 0.0
        self.leave_days = self._get_remaining_annual_leave_days()

        # PART A: UNUTILIZED LEAVE PAYMENT
        DAYS_IN_MONTH = 26
        
        daily_wage = self.wage / DAYS_IN_MONTH
        leave_pay_gross = daily_wage * self.leave_days
        self.leave_pay_gross = round(leave_pay_gross, 2)
        
        leave_pay_per_month = leave_pay_gross / 12.0
        tax_included_annual = self.wage + leave_pay_per_month
        less_tax_1 = self._calculate_dynamic_tax(tax_included_annual)
        less_tax_2 = self._calculate_dynamic_tax(self.wage)
        tax_difference = less_tax_1 - less_tax_2
        leave_pay_tax = tax_difference * 12.0
        self.leave_pay_tax = round(leave_pay_tax, 2)

        # PART B: SALARY & BENEFITS (PRESENT DAYS)
        resig_date = self.resignation_date
        
        present_days = resig_date.day
        self.present_days = present_days
        
        if present_days > 30: present_days = 30
        
        ratio = present_days / 30.0
        
        unpaid_salary = self.wage * ratio
        self.unpaid_salary = round(unpaid_salary, 2)
        
        trans_allowance = getattr(self.employee_id, 'transport_allowance_amount', 0.0)
        self.unpaid_transport = round(trans_allowance * ratio, 2)
        
        rep_fixed = getattr(self.employee_id, 'representation_allowance_fixed', 0.0)
        if rep_fixed > 0:
            rep_amount = rep_fixed
        else:
            rep_percentage = self.employee_id.representation_allowance or 0.0
            rep_amount = (rep_percentage / 100.0) * self.wage
        self.representation_allowance = round(rep_amount * ratio, 2)
        
        housing_base = self.employee_id.housing_allowance or 0.0
        self.unpaid_housing = round(housing_base * ratio, 2)
        
        mobile_base = self.employee_id.mobile_allowance or 0.0
        self.unpaid_mobile = round(mobile_base * ratio, 2)
        
        gross_amount = (self.unpaid_salary + self.unpaid_transport + self.representation_allowance + 
                        self.unpaid_housing + self.unpaid_mobile)
        self.gross_amount = round(gross_amount, 2)
        
        self.taxable_amount = max(0.0, self.gross_amount - 600.0)
        self.tax_salary = self._calculate_dynamic_tax(self.taxable_amount)
        
        self.pension_emp = round(self.unpaid_salary * 0.07, 2)
        self.pension_comp = round(self.unpaid_salary * 0.11, 2)
        
        if self.lost_id_card:
            self.vat_on_id_card = round(self.lost_id_card * 0.15, 2)
            
        self.total_deduction = self.grand_tax + self.pension_emp + self.lost_id_card + self.vat_on_id_card + self.other_deductions
        
        self.net_payable = max(0.0, self.leave_pay_gross + self.gross_amount - self.total_deduction)

    def _calculate_dynamic_tax(self, income):
        if income <= 0:
            return 0.0
        
        brackets = self.env['ahadu.payroll.tax.bracket'].search([
            ('active', '=', True)
        ], order='lower_bound asc')
        
        for bracket in brackets:
            if bracket.lower_bound <= income and (bracket.upper_bound == 0 or income <= bracket.upper_bound):
                tax = (income * (bracket.rate / 100.0)) - bracket.deduction
                return max(0.0, round(tax, 2))
        
        return 0.0

    def _get_remaining_annual_leave_days(self):
        leave_type = None
        try:
            leave_type = self.env.ref('ahadu_hr_leave.ahadu_leave_type_annual', raise_if_not_found=False)
        except:
             pass
        
        if not leave_type:
             leave_type = self.env['hr.leave.type'].search(['|', ('name', '=', 'ahadu_leave_type_annual'), ('name', 'ilike', 'Annual')], limit=1)

        if not leave_type:
            return 0.0

        allocations = self.env['hr.leave.allocation'].search([
            ('employee_id', '=', self.employee_id.id),
            ('holiday_status_id', '=', leave_type.id),
            ('state', '=', 'validate'),
        ])
        
        total_days = sum(allocations.mapped('effective_remaining_leaves')) if allocations else 0.0
        return total_days

    def action_confirm(self):
        for rec in self:
            rec._check_manager_only()
            rec.approved_by_id = self.env.user.id
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancel'})
