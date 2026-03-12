# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

class AhaduComparativeAnalytics(models.TransientModel):
    _name = 'ahadu.comparative.analytics'
    _description = 'Comparative Analytics Dashboard'

    date_from = fields.Date(string='Date From', required=True, default=lambda self: date.today().replace(day=1))
    date_to = fields.Date(string='Date To', required=True, default=lambda self: (date.today().replace(day=1) + relativedelta(months=1)) - timedelta(days=1))
    branch_id = fields.Many2one('hr.branch', string='Branch', help="Select branch to filter analytics. Leave empty for all (HO only).")
    is_head_office = fields.Boolean(compute='_compute_is_head_office')

    # Summary Counts - Current Period
    additions_cur = fields.Integer(string='New Additions (Current)')
    promotions_cur = fields.Integer(string='Promotions (Current)')
    transfers_cur = fields.Integer(string='Transfers (Current)')
    terminations_cur = fields.Integer(string='Terminations (Current)')
    salary_cur = fields.Integer(string='Salary Adjustments (Current)')
    demotions_cur = fields.Integer(string='Demotions (Current)')
    acting_cur = fields.Integer(string='Acting Assignments (Current)')
    temporary_cur = fields.Integer(string='Temporary Assignments (Current)')

    # Summary Counts - Previous Period
    additions_prev = fields.Integer(string='New Additions (Previous)')
    promotions_prev = fields.Integer(string='Promotions (Previous)')
    transfers_prev = fields.Integer(string='Transfers (Previous)')
    terminations_prev = fields.Integer(string='Terminations (Previous)')
    salary_prev = fields.Integer(string='Salary Adjustments (Previous)')
    demotions_prev = fields.Integer(string='Demotions (Previous)')
    acting_prev = fields.Integer(string='Acting Assignments (Previous)')
    temporary_prev = fields.Integer(string='Temporary Assignments (Previous)')

    # Variances
    additions_var = fields.Integer(string='Additions Variance', compute='_compute_variances')
    promotions_var = fields.Integer(string='Promotions Variance', compute='_compute_variances')
    transfers_var = fields.Integer(string='Transfers Variance', compute='_compute_variances')
    terminations_var = fields.Integer(string='Terminations Variance', compute='_compute_variances')
    salary_var = fields.Integer(string='Salary Variance', compute='_compute_variances')
    demotions_var = fields.Integer(string='Demotions Variance', compute='_compute_variances')
    acting_var = fields.Integer(string='Acting Variance', compute='_compute_variances')
    temporary_var = fields.Integer(string='Temporary Variance', compute='_compute_variances')

    detail_ids = fields.One2many('ahadu.comparative.analytics.detail', 'analytics_id', string='Detailed Changes')

    @api.depends('additions_cur', 'additions_prev', 'promotions_cur', 'promotions_prev', 
                 'transfers_cur', 'transfers_prev', 'terminations_cur', 'terminations_prev',
                 'salary_cur', 'salary_prev', 'demotions_cur', 'demotions_prev',
                 'acting_cur', 'acting_prev', 'temporary_cur', 'temporary_prev')
    def _compute_variances(self):
        for rec in self:
            rec.additions_var = rec.additions_cur - rec.additions_prev
            rec.promotions_var = rec.promotions_cur - rec.promotions_prev
            rec.transfers_var = rec.transfers_cur - rec.transfers_prev
            rec.terminations_var = rec.terminations_cur - rec.terminations_prev
            rec.salary_var = rec.salary_cur - rec.salary_prev
            rec.demotions_var = rec.demotions_cur - rec.demotions_prev
            rec.acting_var = rec.acting_cur - rec.acting_prev
            rec.temporary_var = rec.temporary_cur - rec.temporary_prev

    def _compute_is_head_office(self):
        is_ho = self.env.user.has_group('ahadu_payroll.group_head_office_payroll_officer') or \
                 self.env.user.has_group('ahadu_payroll.group_head_office_payroll')
        for rec in self:
            rec.is_head_office = is_ho
            if not is_ho and not rec.branch_id:
                rec.branch_id = self.env.user.employee_id.branch_id

    def action_refresh(self):
        self.ensure_one()
        # Dates for current period
        start_date = self.date_from
        end_date = self.date_to
        
        # Calculate duration of current period to find previous period
        duration = (end_date - start_date).days + 1
        prev_start = start_date - timedelta(days=duration)
        prev_end = start_date - timedelta(days=1)

        # Base domains
        branch_domain = []
        if self.branch_id:
            branch_domain = [('branch_id', '=', self.branch_id.id)]
        
        # Helper to join domains
        def get_domain(date_field, start, end, extra=[]):
            # For promotions, transfers, etc., branch is linked via employee
            dom = [(date_field, '>=', start), (date_field, '<=', end)] + extra
            if self.branch_id:
                dom += [('employee_id.branch_id', '=', self.branch_id.id)]
            return dom

        def get_emp_domain(date_field, start, end):
            # For hr.employee, branch_id is a direct field
            dom = [(date_field, '>=', start), (date_field, '<=', end)]
            if self.branch_id:
                dom += [('branch_id', '=', self.branch_id.id)]
            return dom


        # Current Period Data
        self.additions_cur = self.env['hr.employee'].search_count(get_emp_domain('date_of_joining', start_date, end_date))
        self.promotions_cur = self.env['hr.employee.promotion'].search_count(get_domain('promotion_date', start_date, end_date, [('state', '=', 'approved')]))
        self.transfers_cur = self.env['hr.employee.transfer'].search_count(get_domain('transfer_date', start_date, end_date, [('state', '=', 'approved')]))
        self.terminations_cur = self.env['hr.employee.termination'].search_count(get_domain('termination_date', start_date, end_date, [('state', '=', 'approved')]))
        self.salary_cur = self.env['hr.employee.promotion'].search_count(get_domain('promotion_date', start_date, end_date, [('state', '=', 'approved'), ('new_salary', '>', 0)]))
        self.demotions_cur = self.env['hr.employee.demotion'].search_count(get_domain('demotion_date', start_date, end_date, [('state', '=', 'approved')]))
        self.acting_cur = self.env['hr.employee.acting'].search_count(get_domain('start_date', start_date, end_date, [('state', '=', 'approved')]))
        self.temporary_cur = self.env['hr.employee.temporary.assignment'].search_count(get_domain('start_date', start_date, end_date, [('state', '=', 'approved')]))

        # Previous Period Data
        self.additions_prev = self.env['hr.employee'].search_count(get_emp_domain('date_of_joining', prev_start, prev_end))
        self.promotions_prev = self.env['hr.employee.promotion'].search_count(get_domain('promotion_date', prev_start, prev_end, [('state', '=', 'approved')]))
        self.transfers_prev = self.env['hr.employee.transfer'].search_count(get_domain('transfer_date', prev_start, prev_end, [('state', '=', 'approved')]))
        self.terminations_prev = self.env['hr.employee.termination'].search_count(get_domain('termination_date', prev_start, prev_end, [('state', '=', 'approved')]))
        self.salary_prev = self.env['hr.employee.promotion'].search_count(get_domain('promotion_date', prev_start, prev_end, [('state', '=', 'approved'), ('new_salary', '>', 0)]))
        self.demotions_prev = self.env['hr.employee.demotion'].search_count(get_domain('demotion_date', prev_start, prev_end, [('state', '=', 'approved')]))
        self.acting_prev = self.env['hr.employee.acting'].search_count(get_domain('start_date', prev_start, prev_end, [('state', '=', 'approved')]))
        self.temporary_prev = self.env['hr.employee.temporary.assignment'].search_count(get_domain('start_date', prev_start, prev_end, [('state', '=', 'approved')]))

        # Clear and rebuild details
        self.detail_ids.unlink()
        details = []

        # 1. Additions Details
        for emp in self.env['hr.employee'].search(get_emp_domain('date_of_joining', start_date, end_date)):
            details.append((0, 0, {
                'employee_id': emp.id,
                'change_type': 'addition',
                'change_date': emp.date_of_joining,
                'new_salary': emp.emp_wage,
                'to_job_id': emp.job_id.id,
                'to_dept_id': emp.department_id.id,
                'to_branch_id': emp.branch_id.id,
                'to_division_id': emp.division_id.id,
                'to_cost_center_id': emp.cost_center_id.id,
                'description': _('New Hire - Position: %s') % (emp.job_id.name or 'N/A')
            }))

        # 2. Promotions Details
        for prom in self.env['hr.employee.promotion'].search(get_domain('promotion_date', start_date, end_date, [('state', '=', 'approved')])):
            details.append((0, 0, {
                'employee_id': prom.employee_id.id,
                'change_type': 'promotion',
                'change_date': prom.promotion_date,
                'old_salary': prom.current_salary,
                'new_salary': prom.new_salary,
                'from_job_id': prom.current_job_id.id,
                'to_job_id': prom.new_job_id.id,
                'description': _('Promoted to %s') % (prom.new_job_id.name or 'N/A')
            }))

        # 3. Transfers Details
        for trans in self.env['hr.employee.transfer'].search(get_domain('transfer_date', start_date, end_date, [('state', '=', 'approved')])):
            details.append((0, 0, {
                'employee_id': trans.employee_id.id,
                'change_type': 'transfer',
                'change_date': trans.transfer_date,
                'from_branch_id': trans.current_branch_id.id,
                'to_branch_id': trans.new_branch_id.id,
                'from_dept_id': trans.current_department_id.id,
                'to_dept_id': trans.new_department_id.id,
                'from_division_id': trans.current_division_id.id,
                'to_division_id': trans.new_division_id.id,
                'from_cost_center_id': trans.current_cost_center_id.id,
                'to_cost_center_id': trans.new_cost_center_id.id,
                'from_job_id': trans.current_job_id.id,
                'to_job_id': trans.new_job_id.id,
                'description': _('Transferred to %s') % (trans.new_branch_id.name or 'N/A')
            }))

        # 4. Demotions Details
        for dem in self.env['hr.employee.demotion'].search(get_domain('demotion_date', start_date, end_date, [('state', '=', 'approved')])):
            details.append((0, 0, {
                'employee_id': dem.employee_id.id,
                'change_type': 'demotion',
                'change_date': dem.demotion_date,
                'from_job_id': dem.current_job_id.id,
                'to_job_id': dem.new_job_id.id,
                'from_branch_id': dem.current_branch_id.id,
                'to_branch_id': dem.new_branch_id.id,
                'from_dept_id': dem.current_department_id.id,
                'to_dept_id': dem.new_department_id.id,
                'from_division_id': dem.current_division_id.id,
                'to_division_id': dem.new_division_id.id,
                'from_cost_center_id': dem.current_cost_center_id.id,
                'to_cost_center_id': dem.new_cost_center_id.id,
                'description': _('Demoted to %s') % (dem.new_job_id.name or 'N/A')
            }))

        # 5. Acting Details
        for act in self.env['hr.employee.acting'].search(get_domain('start_date', start_date, end_date, [('state', '=', 'approved')])):
            details.append((0, 0, {
                'employee_id': act.employee_id.id,
                'change_type': 'acting',
                'change_date': act.start_date,
                'to_job_id': act.acting_job_id.id,
                'allowance_amount': act.allowance_amount,
                'description': _('Acting as %s') % (act.acting_job_id.name or 'N/A')
            }))

        # 6. Temporary Assignment Details
        for temp in self.env['hr.employee.temporary.assignment'].search(get_domain('start_date', start_date, end_date, [('state', '=', 'approved')])):
            details.append((0, 0, {
                'employee_id': temp.employee_id.id,
                'change_type': 'temporary',
                'change_date': temp.start_date,
                'from_branch_id': temp.current_branch_id.id,
                'to_branch_id': temp.new_branch_id.id,
                'from_dept_id': temp.current_department_id.id,
                'to_dept_id': temp.new_department_id.id,
                'from_division_id': temp.current_division_id.id,
                'to_division_id': temp.new_division_id.id,
                'from_cost_center_id': temp.current_cost_center_id.id,
                'to_cost_center_id': temp.new_cost_center_id.id,
                # 'from_job_id': temp.current_job_id.id, # hr.employee.temporary.assignment doesn't seem to have job?
                'description': _('Temporary Assignment to %s') % (temp.new_branch_id.name or 'N/A')
            }))

        # 7. Terminations Details
        for term in self.env['hr.employee.termination'].search(get_domain('termination_date', start_date, end_date, [('state', '=', 'approved')])):
            details.append((0, 0, {
                'employee_id': term.employee_id.id,
                'change_type': 'termination',
                'change_date': term.termination_date,
                'description': term.reason or _('Termination')
            }))

        self.detail_ids = details
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ahadu.comparative.analytics',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_generate_excel(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/ahadu_payroll/comparative_analytics_excel/%s' % self.id,
            'target': 'self',
        }

class AhaduComparativeAnalyticsDetail(models.TransientModel):
    _name = 'ahadu.comparative.analytics.detail'
    _description = 'Comparative Analytics Detail'

    analytics_id = fields.Many2one('ahadu.comparative.analytics', ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Employee')
    change_type = fields.Selection([
        ('addition', 'New Addition'),
        ('promotion', 'Promotion'),
        ('transfer', 'Transfer'),
        ('demotion', 'Demotion'),
        ('acting', 'Acting Assignment'),
        ('temporary', 'Temporary Assignment'),
        ('termination', 'Termination'),
        ('salary', 'Salary Adjustment')
    ], string='Change Type')
    change_date = fields.Date(string='Date')
    old_salary = fields.Float(string='Old Salary')
    new_salary = fields.Float(string='New Salary')
    allowance_amount = fields.Float(string='Allowance')
    
    # From/To fields for Excel
    from_job_id = fields.Many2one('hr.job', string='From Position')
    to_job_id = fields.Many2one('hr.job', string='To Position')
    from_branch_id = fields.Many2one('hr.branch', string='From Branch')
    to_branch_id = fields.Many2one('hr.branch', string='To Branch')
    from_dept_id = fields.Many2one('hr.department', string='From Department')
    to_dept_id = fields.Many2one('hr.department', string='To Department')
    from_division_id = fields.Many2one('hr.division', string='From Division')
    to_division_id = fields.Many2one('hr.division', string='To Division')
    from_cost_center_id = fields.Many2one('hr.cost.center', string='From Cost Center')
    to_cost_center_id = fields.Many2one('hr.cost.center', string='To Cost Center')
    
    description = fields.Text(string='Details')


