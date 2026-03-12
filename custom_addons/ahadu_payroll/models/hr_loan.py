from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date
from dateutil.relativedelta import relativedelta

class HrLoan(models.Model):
    _name = 'hr.loan'
    _description = 'Employee Loan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Loan Reference', readonly=True, copy=False, default='New')
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, tracking=True)
    loan_type_id = fields.Many2one('hr.loan.type', string='Loan Type', required=True, tracking=True)
    
    principal_amount = fields.Monetary(string='Requested Amount', required=True, tracking=True)
    interest_rate = fields.Float(string='Interest Rate (%)', related='loan_type_id.interest_rate', readonly=False, store=True)
    installment_months = fields.Integer(string='Installment Period (Months)', required=True, tracking=True)
    monthly_installment = fields.Monetary(string='Monthly Installment', compute='_compute_installment', store=True)
    total_repayment = fields.Monetary(string='Total Repayment', compute='_compute_installment', store=True)
    total_interest = fields.Monetary(string='Total Interest', compute='_compute_installment', store=True)

    date_request = fields.Date(string='Request Date', default=fields.Date.context_today, readonly=True)
    date_start = fields.Date(string='Payment Start Date', required=True, tracking=True)
    
    currency_id = fields.Many2one('res.currency', related='employee_id.currency_id')
    
    bank_account_id = fields.Many2one(
        'hr.employee.bank.account', 
        string='Disbursement Account',
        required=True,
        help="Bank account where the loan will be disbursed.",
        domain="[('employee_id', '=', employee_id)]"
    )

    @api.onchange('employee_id')
    def _onchange_employee_id_bank(self):
        if self.employee_id:
            # Pick 'salary' account if it exists, else the first one
            accounts = self.env['hr.employee.bank.account'].sudo().search([('employee_id', '=', self.employee_id.id)])
            if accounts:
                salary_acc = accounts.filtered(lambda a: a.account_type == 'salary')
                self.bank_account_id = salary_acc[0] if salary_acc else accounts[0]
            else:
                self.bank_account_id = False
        else:
            self.bank_account_id = False
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('committee_approval', 'Waiting Credit Committee'),
        ('approved', 'Approved'),
        ('completed', 'Completed'),
        ('refused', 'Refused'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    is_spouse_income_used = fields.Boolean(string="Spouse's Income Used", tracking=True)
    spouse_income_deposit_required = fields.Boolean(
        string='Spouse Salary Deposit Required', 
        compute='_compute_spouse_deposit',
        help="If spouse income is used, borrower must deposit spouse's salary."
    )
    
    refusal_reason = fields.Text(string='Refusal Reason', tracking=True)

    paid_installments = fields.Integer(string='Paid Installments', default=0, tracking=True)
    remaining_amount = fields.Monetary(string='Remaining Amount', compute='_compute_remaining', store=True)
    
    is_editable = fields.Boolean(compute='_compute_is_editable')

    retirement_date = fields.Date(string='Projected Retirement Date', compute='_compute_eligibility', store=True)
    max_settlement_date = fields.Date(string='Max Settlement Date', compute='_compute_eligibility', store=True)
    
    document_ids = fields.One2many('hr.loan.document', 'loan_id', string='Documents')
    
    @api.depends('employee_id')
    def _compute_eligibility(self):
        for rec in self:
            if rec.employee_id and rec.employee_id.birthday:
                # Retirement at 60
                retirement_date = rec.employee_id.birthday + relativedelta(years=60)
                rec.retirement_date = retirement_date
                # Settle 1 year before retirement
                rec.max_settlement_date = retirement_date - relativedelta(years=1)
            else:
                rec.retirement_date = False
                rec.max_settlement_date = False

    @api.depends('principal_amount', 'interest_rate', 'installment_months')
    def _compute_installment(self):
        for rec in self:
            if rec.principal_amount and rec.installment_months > 0:
                # Flat rate: Total Interest = Principal * rate/100 * (months/12)
                total_interest = rec.principal_amount * (rec.interest_rate / 100.0) * (rec.installment_months / 12.0)
                total_repayment = rec.principal_amount + total_interest
                rec.total_interest = total_interest
                rec.total_repayment = total_repayment
                rec.monthly_installment = total_repayment / rec.installment_months
            else:
                rec.total_interest = 0
                rec.total_repayment = 0
                rec.monthly_installment = 0

    @api.depends('is_spouse_income_used')
    def _compute_spouse_deposit(self):
        for rec in self:
            rec.spouse_income_deposit_required = rec.is_spouse_income_used

    @api.depends('total_repayment', 'paid_installments', 'monthly_installment')
    def _compute_remaining(self):
        for rec in self:
            rec.remaining_amount = max(0, rec.total_repayment - (rec.paid_installments * rec.monthly_installment))

    def increment_paid_installment(self):
        for rec in self:
            rec.paid_installments += 1
            if rec.paid_installments >= rec.installment_months:
                rec.state = 'completed'

    @api.depends('state')
    def _compute_is_editable(self):
        is_manager = self.env.user.has_group('ahadu_payroll.group_branch_payroll_manager') or \
                     self.env.user.has_group('ahadu_payroll.group_head_office_payroll') or \
                     self.env.user.has_group('base.group_system')
        for rec in self:
            if not rec.state or rec.state == 'draft':
                rec.is_editable = True
            elif rec.state == 'approved' and is_manager:
                rec.is_editable = True
            else:
                rec.is_editable = False

    def action_submit(self):
        self._check_loan_validation()
        self._check_mandatory_documents()
        for rec in self:
            if rec.loan_type_id.is_credit_committee_required:
                rec.write({'state': 'committee_approval'})
            else:
                rec.write({'state': 'approved'})

    def action_committee_approve(self):
        self.write({'state': 'approved'})

    def action_refuse(self):
        return {
            'name': _('Refusal Reason'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.loan.refuse.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_loan_id': self.id},
        }

    def _check_mandatory_documents(self):
        # Requirements list Application Letter, Amount, Salary info, Marriage cert, TIN, Collateral, etc.
        # This will be enforced by documents model
        for rec in self:
            mandatory_types = ['application', 'salary_info', 'tin', 'collateral']
            provided_types = rec.document_ids.mapped('document_type')
            for m_type in mandatory_types:
                if m_type not in provided_types:
                    raise ValidationError(_("Missing mandatory document: %s") % m_type)

    def _check_loan_validation(self):
        for rec in self:
            # 1. Eligibility Months from DOJ
            if rec.employee_id.date_of_joining:
                diff = relativedelta(date.today(), rec.employee_id.date_of_joining)
                months_service = diff.years * 12 + diff.months
                if months_service < rec.loan_type_id.eligibility_months_doj:
                    raise ValidationError(_("Employee must have at least %s months of service for this loan.") % rec.loan_type_id.eligibility_months_doj)
            else:
                raise ValidationError(_("Employee Date of Joining is required for eligibility check."))

            # 2. Retirement Settlement Rule
            if rec.date_start and rec.max_settlement_date:
                planned_end = rec.date_start + relativedelta(months=rec.installment_months)
                if planned_end > rec.max_settlement_date:
                    raise ValidationError(_("Loan must be settled before %s (1 year before retirement).") % rec.max_settlement_date)

            # 3. Probation Check
            probation = self.env['hr.employee.probation'].search([
                ('employee_id', '=', rec.employee_id.id),
                ('state', 'in', ['draft', 'submitted'])
            ], limit=1)
            if probation:
                raise ValidationError(_("Employees on probation cannot take any type of loan."))

            # 4. Employment Type Check (No Contract or Temporary)
            emp_type_code = rec.employee_id.ahadu_employee_type_id.code
            if emp_type_code in ['contract', 'temporary']:
                raise ValidationError(_("Contract or Temporary employees are not allowed to take loans."))

            # 5. Loan Limit (Basic Salary * Multiple)
            basic_salary = rec.employee_id.emp_wage or 0.0
            loan_limit = basic_salary * rec.loan_type_id.salary_multiple_limit
            if rec.principal_amount > loan_limit:
                raise ValidationError(_("Requested amount exceeds the loan limit of %s (Basic Salary * %s).") % (loan_limit, rec.loan_type_id.salary_multiple_limit))

            # 6. Max Installment Months Check
            if rec.installment_months > rec.loan_type_id.max_installment_months:
                raise ValidationError(_("Installment period cannot be greater than max installment for that loan type"))

    @api.constrains('installment_months', 'loan_type_id')
    def _check_max_installment(self):
        for rec in self:
            if rec.loan_type_id and rec.installment_months > rec.loan_type_id.max_installment_months:
                raise ValidationError(_("Installment period cannot be greater than max installment for that loan type"))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.loan') or 'New'
        return super().create(vals_list)

class HrLoanDocument(models.Model):
    _name = 'hr.loan.document'
    _description = 'Loan Mandatory Document'

    loan_id = fields.Many2one('hr.loan', string='Loan', ondelete='cascade')
    document_type = fields.Selection([
        ('application', 'Application Letter'),
        ('salary_info', 'Salary Information from HR'),
        ('marriage_cert', 'Married/Unmarried Certificate'),
        ('tin', 'TIN Document'),
        ('collateral', 'Collateral Detail'),
        ('other', 'Other Supportive Document')
    ], string='Document Type', required=True)
    attachment = fields.Binary(string='Attachment', required=True)
    attachment_filename = fields.Char(string='Attachment Filename')
    notes = fields.Text(string='Notes')
