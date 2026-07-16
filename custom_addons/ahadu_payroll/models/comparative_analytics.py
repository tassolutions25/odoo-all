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
    department_id = fields.Many2one('hr.department', string='Department', help="Select department to filter analytics. Leave empty for all.")
    region_id = fields.Many2one('hr.region', string='Region', help="Select region to filter analytics. Leave empty for all.")
    pay_group_id = fields.Many2one('ahadu.pay.group', string='Pay Group', help="Select pay group to filter analytics. Leave empty for all.")
    is_head_office = fields.Boolean(compute='_compute_is_head_office')

    # Headcount Summary
    headcount_prev = fields.Integer(string='Employees at Start of Period')
    headcount_cur = fields.Integer(string='Employees at End of Period')

    # Summary Counts - Current Period
    additions_cur = fields.Integer(string='New Additions (Current)')
    promotions_cur = fields.Integer(string='Promotions (Current)')
    transfers_cur = fields.Integer(string='Transfers (Current)')
    terminations_cur = fields.Integer(string='Terminations (Current)')
    salary_cur = fields.Integer(string='Salary Adjustments (Current)')
    demotions_cur = fields.Integer(string='Demotions (Current)')
    acting_cur = fields.Integer(string='Acting Assignments (Current)')
    temporary_cur = fields.Integer(string='Temporary Assignments (Current)')
    suspensions_cur = fields.Integer(string='Suspensions (Current)')

    # Summary Counts - Previous Period
    additions_prev = fields.Integer(string='New Additions (Previous)')
    promotions_prev = fields.Integer(string='Promotions (Previous)')
    transfers_prev = fields.Integer(string='Transfers (Previous)')
    terminations_prev = fields.Integer(string='Terminations (Previous)')
    salary_prev = fields.Integer(string='Salary Adjustments (Previous)')
    demotions_prev = fields.Integer(string='Demotions (Previous)')
    acting_prev = fields.Integer(string='Acting Assignments (Previous)')
    temporary_prev = fields.Integer(string='Temporary Assignments (Previous)')
    suspensions_prev = fields.Integer(string='Suspensions (Previous)')

    # Variances
    additions_var = fields.Integer(string='Additions Variance', compute='_compute_variances')
    promotions_var = fields.Integer(string='Promotions Variance', compute='_compute_variances')
    transfers_var = fields.Integer(string='Transfers Variance', compute='_compute_variances')
    terminations_var = fields.Integer(string='Terminations Variance', compute='_compute_variances')
    salary_var = fields.Integer(string='Salary Variance', compute='_compute_variances')
    demotions_var = fields.Integer(string='Demotions Variance', compute='_compute_variances')
    acting_var = fields.Integer(string='Acting Variance', compute='_compute_variances')
    temporary_var = fields.Integer(string='Temporary Variance', compute='_compute_variances')
    suspensions_var = fields.Integer(string='Suspensions Variance', compute='_compute_variances')

    detail_ids = fields.One2many('ahadu.comparative.analytics.detail', 'analytics_id', string='Detailed Changes')

    @api.depends('additions_cur', 'additions_prev', 'promotions_cur', 'promotions_prev', 
                 'transfers_cur', 'transfers_prev', 'terminations_cur', 'terminations_prev',
                 'salary_cur', 'salary_prev', 'demotions_cur', 'demotions_prev',
                 'acting_cur', 'acting_prev', 'temporary_cur', 'temporary_prev',
                 'suspensions_cur', 'suspensions_prev')
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
            rec.suspensions_var = rec.suspensions_cur - rec.suspensions_prev

    def _compute_is_head_office(self):
        is_ho = self.env.user.has_group('ahadu_payroll.group_head_office_payroll_officer') or \
                 self.env.user.has_group('ahadu_payroll.group_head_office_payroll')
        for rec in self:
            rec.is_head_office = is_ho
            if not is_ho and not rec.branch_id:
                rec.branch_id = self.env.user.employee_id.branch_id

    def get_headcount_at_date(self, target_date):
        # 1. Fetch all employees whose date_of_joining <= target_date
        employees = self.env['hr.employee'].sudo().with_context(active_test=False).search([
            ('date_of_joining', '<=', target_date),
            ('date_of_joining', '!=', False)
        ])
        
        # 2. Filter out those who departed on or before target_date
        valid_employees = []
        for emp in employees:
            if not emp.active and emp.departure_date and emp.departure_date <= target_date:
                continue
            termination = self.env['hr.employee.termination'].sudo().search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'approved'),
                ('termination_date', '<=', target_date)
            ], limit=1)
            if termination:
                continue
            valid_employees.append(emp)
            
        # 3. For each valid employee, find their branch, department, region, pay group as of target_date
        count = 0
        for emp in valid_employees:
            earliest_transfer = self.env['hr.employee.transfer'].sudo().search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'approved'),
                ('transfer_date', '>', target_date)
            ], order='transfer_date asc, id asc', limit=1)
            
            if earliest_transfer:
                branch = earliest_transfer.current_branch_id
                dept = earliest_transfer.current_department_id
            else:
                branch = emp.branch_id
                dept = emp.department_id
                
            region = branch.region_id if branch else emp.region_id
            pay_group = emp.contract_id.pay_group_id
            
            # Apply filters safely comparing IDs to prevent context/environment mismatches
            if self.branch_id and branch.id != self.branch_id.id:
                continue
            if self.department_id and dept.id != self.department_id.id:
                continue
            if self.region_id and region.id != self.region_id.id:
                continue
            if self.pay_group_id and pay_group.id != self.pay_group_id.id:
                continue
                
            count += 1
            
        return count

    def action_refresh(self):
        self.ensure_one()
        # Dates for current period
        start_date = self.date_from
        end_date = self.date_to
        
        # Calculate duration of current period to find previous period
        duration = (end_date - start_date).days + 1
        prev_start = start_date - timedelta(days=duration)
        prev_end = start_date - timedelta(days=1)

        def employee_matches(emp):
            if self.branch_id and emp.branch_id.id != self.branch_id.id:
                return False
            if self.department_id and emp.department_id.id != self.department_id.id:
                return False
            region = emp.branch_id.region_id or emp.region_id
            if self.region_id and region.id != self.region_id.id:
                return False
            if self.pay_group_id and emp.contract_id.pay_group_id.id != self.pay_group_id.id:
                return False
            return True

        def field_ids(record, field_names):
            ids = set()
            for field_name in field_names:
                if field_name in record._fields and record[field_name]:
                    ids.add(record[field_name].id)
            return ids

        def activity_matches(activity):
            employee = activity.employee_id

            branch_ids = field_ids(activity, ['current_branch_id', 'new_branch_id'])
            if not branch_ids and employee.branch_id:
                branch_ids.add(employee.branch_id.id)
            if self.branch_id and self.branch_id.id not in branch_ids:
                return False

            dept_ids = field_ids(activity, ['current_department_id', 'new_department_id'])
            if not dept_ids and employee.department_id:
                dept_ids.add(employee.department_id.id)
            if self.department_id and self.department_id.id not in dept_ids:
                return False

            if self.region_id:
                branches = self.env['hr.branch'].browse(list(branch_ids))
                region_ids = set(branches.mapped('region_id').ids)
                if not region_ids and employee.region_id:
                    region_ids.add(employee.region_id.id)
                if self.region_id.id not in region_ids:
                    return False

            if self.pay_group_id and employee.contract_id.pay_group_id.id != self.pay_group_id.id:
                return False

            return True

        def get_activities(model_name, date_field, start, end, extra=None, use_sudo=False):
            model = self.env[model_name].sudo() if use_sudo else self.env[model_name]
            domain = [(date_field, '>=', start), (date_field, '<=', end)] + (extra or [])
            return model.search(domain).filtered(activity_matches)

        def get_employees(date_field, start, end):
            return self.env['hr.employee'].search([
                (date_field, '>=', start),
                (date_field, '<=', end)
            ]).filtered(employee_matches)


        # Current Period Data
        additions = get_employees('date_of_joining', start_date, end_date)
        promotions = get_activities('hr.employee.promotion', 'promotion_date', start_date, end_date, [('state', '=', 'approved')])
        transfers = get_activities('hr.employee.transfer', 'transfer_date', start_date, end_date, [('state', '=', 'approved')])
        terminations = get_activities('hr.employee.termination', 'termination_date', start_date, end_date, [('state', '=', 'approved')])
        salary_adjustments = get_activities('hr.employee.promotion', 'promotion_date', start_date, end_date, [('state', '=', 'approved'), ('new_salary', '>', 0)])
        demotions = get_activities('hr.employee.demotion', 'demotion_date', start_date, end_date, [('state', '=', 'approved')])
        acting_assignments = get_activities('hr.employee.acting', 'start_date', start_date, end_date, [('state', '=', 'approved')])
        temporary_assignments = get_activities('hr.employee.temporary.assignment', 'start_date', start_date, end_date, [('state', '=', 'approved')])
        suspensions = get_activities('hr.employee.suspension', 'start_date', start_date, end_date, [('state', 'in', ['approved', 'Approved'])], use_sudo=True)

        self.additions_cur = len(additions)
        self.promotions_cur = len(promotions)
        self.transfers_cur = len(transfers)
        self.terminations_cur = len(terminations)
        self.salary_cur = len(salary_adjustments)
        self.demotions_cur = len(demotions)
        self.acting_cur = len(acting_assignments)
        self.temporary_cur = len(temporary_assignments)
        self.suspensions_cur = len(suspensions)

        # Previous Period Data
        self.additions_prev = len(get_employees('date_of_joining', prev_start, prev_end))
        self.promotions_prev = len(get_activities('hr.employee.promotion', 'promotion_date', prev_start, prev_end, [('state', '=', 'approved')]))
        self.transfers_prev = len(get_activities('hr.employee.transfer', 'transfer_date', prev_start, prev_end, [('state', '=', 'approved')]))
        self.terminations_prev = len(get_activities('hr.employee.termination', 'termination_date', prev_start, prev_end, [('state', '=', 'approved')]))
        self.salary_prev = len(get_activities('hr.employee.promotion', 'promotion_date', prev_start, prev_end, [('state', '=', 'approved'), ('new_salary', '>', 0)]))
        self.demotions_prev = len(get_activities('hr.employee.demotion', 'demotion_date', prev_start, prev_end, [('state', '=', 'approved')]))
        self.acting_prev = len(get_activities('hr.employee.acting', 'start_date', prev_start, prev_end, [('state', '=', 'approved')]))
        self.temporary_prev = len(get_activities('hr.employee.temporary.assignment', 'start_date', prev_start, prev_end, [('state', '=', 'approved')]))
        self.suspensions_prev = len(get_activities('hr.employee.suspension', 'start_date', prev_start, prev_end, [('state', 'in', ['approved', 'Approved'])], use_sudo=True))

        # Headcount Reconciliation
        self.headcount_prev = self.get_headcount_at_date(start_date - timedelta(days=1))
        
        # Calculate transfers_in and transfers_out in current period for headcount reconciliation
        transfers_in = 0
        transfers_out = 0
        all_transfers = self.env['hr.employee.transfer'].search([
            ('transfer_date', '>=', start_date),
            ('transfer_date', '<=', end_date),
            ('state', '=', 'approved')
        ])
        for tr in all_transfers:
            if self.pay_group_id and tr.employee_id.contract_id.pay_group_id.id != self.pay_group_id.id:
                continue
            # Check "before" state safely comparing IDs to prevent context/environment mismatches
            before_match = True
            if self.branch_id and tr.current_branch_id.id != self.branch_id.id:
                before_match = False
            if self.department_id and tr.current_department_id.id != self.department_id.id:
                before_match = False
            if self.region_id and tr.current_branch_id.region_id.id != self.region_id.id:
                before_match = False
            
            # Check "after" state safely comparing IDs
            after_match = True
            if self.branch_id and tr.new_branch_id.id != self.branch_id.id:
                after_match = False
            if self.department_id and tr.new_department_id.id != self.department_id.id:
                after_match = False
            if self.region_id and tr.new_branch_id.region_id.id != self.region_id.id:
                after_match = False
                
            if before_match and not after_match:
                transfers_out += 1
            elif not before_match and after_match:
                transfers_in += 1

        self.headcount_cur = self.headcount_prev + self.additions_cur - transfers_out + transfers_in - self.terminations_cur

        # Clear and rebuild details
        self.detail_ids.unlink()
        details = []

        # 1. Additions Details
        for emp in additions:
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
        for prom in promotions:
            details.append((0, 0, {
                'employee_id': prom.employee_id.id,
                'change_type': 'promotion',
                'change_date': prom.promotion_date,
                'old_salary': prom.current_salary,
                'new_salary': prom.new_salary,
                'from_job_id': prom.current_job_id.id,
                'to_job_id': prom.new_job_id.id,
                'from_branch_id': prom.current_branch_id.id,
                'to_branch_id': (prom.new_branch_id or prom.current_branch_id or prom.employee_id.branch_id).id,
                'from_dept_id': prom.current_department_id.id,
                'to_dept_id': (prom.new_department_id or prom.current_department_id or prom.employee_id.department_id).id,
                'description': _('Promoted to %s') % (prom.new_job_id.name or 'N/A')
            }))

        # 3. Transfers Details
        for trans in transfers:
            from_branch_name = trans.current_branch_id.name or 'N/A'
            to_branch_name = trans.new_branch_id.name or 'N/A'

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
                'description': _('Transferred from %s to %s') % (from_branch_name, to_branch_name)
            }))

        # 4. Demotions Details
        for dem in demotions:
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
        for act in acting_assignments:
            details.append((0, 0, {
                'employee_id': act.employee_id.id,
                'change_type': 'acting',
                'change_date': act.start_date,
                'to_job_id': act.acting_job_id.id,
                'from_branch_id': act.current_branch_id.id,
                'to_branch_id': (act.new_branch_id or act.current_branch_id or act.employee_id.branch_id).id,
                'from_dept_id': act.current_department_id.id,
                'to_dept_id': (act.new_department_id or act.current_department_id or act.employee_id.department_id).id,
                'allowance_amount': act.allowance_amount,
                'description': _('Acting as %s') % (act.acting_job_id.name or 'N/A')
            }))

        # 6. Temporary Assignment Details
        for temp in temporary_assignments:
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
        for term in terminations:
            details.append((0, 0, {
                'employee_id': term.employee_id.id,
                'change_type': 'termination',
                'change_date': term.termination_date,
                'to_branch_id': term.employee_id.branch_id.id,
                'to_dept_id': term.employee_id.department_id.id,
                'description': term.reason or _('Termination')
            }))

        # 8. Suspensions Details
        for susp in suspensions:
            details.append((0, 0, {
                'employee_id': susp.employee_id.id,
                'change_type': 'suspension',
                'change_date': susp.start_date,
                'to_branch_id': susp.employee_id.branch_id.id,
                'to_dept_id': susp.employee_id.department_id.id,
                'description': _('Suspended until %s') % susp.end_date
            }))

        # 9. Salary Adjustments Details
        for prom in salary_adjustments:
            details.append((0, 0, {
                'employee_id': prom.employee_id.id,
                'change_type': 'salary',
                'change_date': prom.promotion_date,
                'old_salary': prom.current_salary,
                'new_salary': prom.new_salary,
                'from_job_id': prom.current_job_id.id,
                'to_job_id': prom.new_job_id.id,
                'from_branch_id': prom.current_branch_id.id,
                'to_branch_id': (prom.new_branch_id or prom.current_branch_id or prom.employee_id.branch_id).id,
                'from_dept_id': prom.current_department_id.id,
                'to_dept_id': (prom.new_department_id or prom.current_department_id or prom.employee_id.department_id).id,
                'description': _('Salary adjusted from %s to %s') % (prom.current_salary, prom.new_salary)
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
        ('salary', 'Salary Adjustment'),
        ('suspension', 'Suspension')
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


