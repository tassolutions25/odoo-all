# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta

class AhaduBonusPayment(models.Model):
    _name = 'ahadu.bonus.payment'
    _description = 'Bonus Payment Run'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Title/Description', required=True, tracking=True)
    date = fields.Date('Date', default=fields.Date.context_today, required=True, tracking=True)
    period_type = fields.Selection([
        ('half', 'Half Year'), 
        ('full', 'Full Year')
    ], string='Period Type', default='half', required=True)
    
    months_of_year = fields.Integer('Months of the Year', default=6, required=True, 
                                    help="Multiplier for final bonus and tax calculation (e.g. 6 for half-year, 12 for full-year)")
    cutoff_date = fields.Date('Cutoff Date (Half/Full Year Date)', required=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('calculated', 'Calculated'),
        ('verified', 'Verified'),
        ('approved', 'Approved'),
        ('done', 'Done')
    ], default='draft', string='Status', tracking=True)

    prepared_by_id = fields.Many2one('res.users', string='Prepared By', readonly=True, tracking=True)
    prepared_on = fields.Datetime(string='Prepared On', readonly=True)
    verified_by_id = fields.Many2one('res.users', string='Verified By', readonly=True, tracking=True)
    verified_on = fields.Datetime(string='Verified On', readonly=True)
    approved_by_id = fields.Many2one('res.users', string='Approved By', readonly=True, tracking=True)
    approved_on = fields.Datetime(string='Approved On', readonly=True)
    
    line_ids = fields.One2many('ahadu.bonus.payment.line', 'bonus_id', string='Employee Bonuses')

    total_bonus_amount = fields.Float('Total Bonus Amount', compute='_compute_totals', store=True)
    total_tax_amount = fields.Float('Total Tax Amount', compute='_compute_totals', store=True)
    total_net_pay = fields.Float('Total Net Pay', compute='_compute_totals', store=True)

    @api.depends('line_ids.bonus_amount', 'line_ids.bonus_tax', 'line_ids.net_bonus_pay')
    def _compute_totals(self):
        for run in self:
            run.total_bonus_amount = sum(run.line_ids.mapped('bonus_amount'))
            run.total_tax_amount = sum(run.line_ids.mapped('bonus_tax'))
            run.total_net_pay = sum(run.line_ids.mapped('net_bonus_pay'))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_manager_restriction()
        for vals in vals_list:
            vals['prepared_by_id'] = self.env.user.id
            vals['prepared_on'] = fields.Datetime.now()
        return super(AhaduBonusPayment, self).create(vals_list)

    def write(self, vals):
        # Allow state changes or technical field updates, but block Draft data edits for Managers
        if any(run.state == 'draft' for run in self):
            if not all(k in ['state', 'message_follower_ids', 'activity_ids', 'message_ids',
                             'prepared_by_id', 'prepared_on', 'verified_by_id', 'verified_on', 
                             'approved_by_id', 'approved_on'] for k in vals.keys()):
                self._check_manager_restriction()
        return super(AhaduBonusPayment, self).write(vals)

    def unlink(self):
        self._check_manager_restriction()
        return super(AhaduBonusPayment, self).unlink()

    def _check_manager_restriction(self):
        """Helper to block Managers from Maker actions."""
        if self.env.user.has_group('payroll.group_payroll_manager'):
            if not self.env.user.has_group('base.group_system'):
                from odoo.exceptions import AccessError
                raise AccessError(_("Payroll Managers are restricted from this action (Create/Edit). This action is reserved for Payroll Officers."))

    def action_generate_employees(self):
        """Fetch all active employees with active contracts before cutoff date"""
        self._check_manager_restriction()
        for run in self:
            if run.state != 'draft':
                raise UserError(_("You can only generate employees in Draft state."))
                
            domain = [
                ('contract_id', '!=', False),
                ('contract_id.date_start', '<=', run.cutoff_date),
            ]
            employees = self.env['hr.employee'].search(domain)
            
            existing_emp_ids = run.line_ids.mapped('employee_id').ids
            employees_to_add = employees.filtered(lambda e: e.id not in existing_emp_ids)
            
            lines = []
            for emp in employees_to_add:
                lines.append((0, 0, {
                    'employee_id': emp.id,
                    'entitlement_multiplier': 2.0 if run.period_type == 'half' else 4.0, # Defaulting some logic 
                }))
            
            if lines:
                run.write({'line_ids': lines})

    def action_calculate(self):
        for run in self:
            for line in run.line_ids:
                line.calculate_bonus()
            run.state = 'calculated'

    def action_verify(self):
        for run in self:
            run.write({
                'state': 'verified',
                'verified_by_id': self.env.user.id,
                'verified_on': fields.Datetime.now()
            })

    def action_approve(self):
        # Ensure only Manager can approve
        if not self.env.user.has_group('payroll.group_payroll_manager'):
             raise UserError(_("Only Payroll Managers can approve bonus payments."))
        for run in self:
            run.write({
                'state': 'approved',
                'approved_by_id': self.env.user.id,
                'approved_on': fields.Datetime.now()
            })

    def action_done(self):
        for run in self:
            run.state = 'done'

    def action_draft(self):
        for run in self:
            if run.state in ('approved', 'done'):
                raise UserError(_("This bonus payment is already Approved or Done. You cannot reset it to Draft."))
            run.state = 'draft'
            
    def action_print_excel(self):
        return {
            'type': 'ir.actions.act_url',
            'url': f'/ahadu_payroll/bonus_excel/{self.id}',
            'target': 'new',
        }

    def action_print_tax_declaration(self):
        return {
            'type': 'ir.actions.act_url',
            'url': f'/ahadu_payroll/bonus_tax_declaration/{self.id}',
            'target': 'new',
        }


class AhaduBonusPaymentLine(models.Model):
    _name = 'ahadu.bonus.payment.line'
    _description = 'Bonus Payment Employee Line'
    
    bonus_id = fields.Many2one('ahadu.bonus.payment', ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', required=True)
    employee_id_code = fields.Char(string='Employee ID', help="Enter Employee ID to quickly find the employee")

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            self.employee_id_code = self.employee_id.identification_id or self.employee_id.employee_id

    @api.onchange('employee_id_code')
    def _onchange_employee_id_code(self):
        if self.employee_id_code:
            employee = self.env['hr.employee'].search([
                '|', ('identification_id', '=', self.employee_id_code),
                ('employee_id', '=', self.employee_id_code)
            ], limit=1)
            if employee:
                self.employee_id = employee.id
            else:
                pass
    
    # Employee Basic Info
    salary_account_number = fields.Char('Salary Account Number', compute='_compute_basic_info', store=True)
    tin_number = fields.Char('TIN Number', related='employee_id.tin_number', store=True)
    employee_id_no = fields.Char('ID No', related='employee_id.identification_id', store=True)
    job_id = fields.Many2one('hr.job', related='employee_id.job_id', store=True)
    employment_date = fields.Date('Employment Date', compute='_compute_basic_info', store=True)
    department_id = fields.Many2one('hr.department', related='employee_id.department_id', store=True)
    branch_id = fields.Many2one('hr.branch', related='employee_id.branch_id', store=True)
    
    is_managerial = fields.Boolean('Managerial', compute='_compute_is_managerial', store=True)
    
    # Entitlement & Period
    monthly_salary = fields.Float('Monthly Salary', compute='_compute_basic_info', store=True)
    total_working_months = fields.Float('Total Working Months', compute='_compute_working_months', store=True)
    entitlement_multiplier = fields.Float('Bonus Entitlement Multiplier', default=2.0)
    
    bonus_entitlement = fields.Float('Bonus Entitlement')
    bonus_per_month = fields.Float('Bonus Per Month')
    
    # Tax Workout
    salary_paid_during_mid = fields.Float('Salary Paid During Period Mid')
    tax_a = fields.Float('Tax - A')
    salary_plus_bonus = fields.Float('Salary Plus Bonus') 
    tax_b = fields.Float('Tax - B')
    tax_difference = fields.Float('Tax Difference')
    
    # Payment to be made
    bonus_amount = fields.Float('Bonus Amount')
    bonus_tax = fields.Float('Bonus Tax')
    net_bonus_pay = fields.Float('Net Bonus Pay')
    
    @api.depends('employee_id')
    def _compute_basic_info(self):
        for line in self:
            if line.employee_id:
                # Get salary account
                salary_account = line.employee_id.bank_account_ids.filtered(lambda a: a.account_type == 'salary')
                line.salary_account_number = salary_account[0].account_number if salary_account else ''
                
                # Get employment date from contract
                contract = line.employee_id.contract_id
                line.employment_date = contract.date_start if contract else False
                
                # Get monthly salary (emp_wage)
                line.monthly_salary = getattr(line.employee_id, 'emp_wage', 0.0)

    @api.depends('employee_id.job_id')
    def _compute_is_managerial(self):
        for line in self:
            is_mgr = False
            if line.employee_id and line.employee_id.job_id:
                # Map using Pay Group
                pay_groups = self.env['ahadu.pay.group'].search([('job_ids', 'in', line.employee_id.job_id.id)])
                for pg in pay_groups:
                    name_lower = pg.name.lower()
                    if 'executive' in name_lower or 'senior management' in name_lower:
                        is_mgr = True
                        break
            line.is_managerial = is_mgr

    @api.depends('employment_date', 'bonus_id.cutoff_date')
    def _compute_working_months(self):
        for line in self:
            if line.employment_date and line.bonus_id and line.bonus_id.cutoff_date:
                start_date = line.employment_date
                end_date = line.bonus_id.cutoff_date
                
                if start_date <= end_date:
                    delta = relativedelta(end_date + relativedelta(days=1), start_date)
                    months = delta.years * 12 + delta.months + (delta.days / 30.0)
                    line.total_working_months = round(months, 2)
                else:
                    line.total_working_months = 0.0
            else:
                line.total_working_months = 0.0

    def calculate_bonus(self):
        """Perform all tax calculations and field updates"""
        self.ensure_one()
        months_of_year = self.bonus_id.months_of_year or 6
        
        # 1. Entitlement
        actual_multiplier = min(self.total_working_months, self.entitlement_multiplier) if self.total_working_months < self.bonus_id.months_of_year else self.entitlement_multiplier
        # Wait, if Dereje worked 6.25 months, multiplier is 2. (Entitlement 250,488 on 125,244)
        # We will strictly do what user said: "Here we multiply the basic salary with the entitlement we set in the entry"
        self.bonus_entitlement = self.monthly_salary * self.entitlement_multiplier
        self.bonus_per_month = self.bonus_entitlement / months_of_year if months_of_year else 0.0
        
        # 2. Tax Workout
        # Note: 'salary paid during year mid is the monthly salary' 
        self.salary_paid_during_mid = self.monthly_salary
        
        self.tax_a = self._get_ahadu_income_tax(self.salary_paid_during_mid)
        
        self.salary_plus_bonus = self.salary_paid_during_mid + self.bonus_per_month
        self.tax_b = self._get_ahadu_income_tax(self.salary_plus_bonus)
        
        self.tax_difference = self.tax_b - self.tax_a
        
        # 3. Payment
        self.bonus_amount = months_of_year * self.bonus_per_month
        self.bonus_tax = months_of_year * self.tax_difference
        self.net_bonus_pay = self.bonus_amount - self.bonus_tax

    def _get_ahadu_income_tax(self, taxable_income):
        """Replicated Ethiopian Tax rule"""
        tax = 0.0
        brackets = self.env['ahadu.payroll.tax.bracket'].search([
            ('active', '=', True)
        ], order='lower_bound asc')
        
        for bracket in brackets:
            lower = bracket.lower_bound
            upper = bracket.upper_bound
            
            is_match = False
            if upper > 0:
                if lower <= taxable_income <= upper:
                    is_match = True
            else:
                if taxable_income >= lower:
                    is_match = True
            
            if is_match:
                tax = (taxable_income * (bracket.rate / 100.0)) - bracket.deduction
                break
                
        return round(max(0, tax), 2)
