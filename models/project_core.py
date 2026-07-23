from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

class ProjectCategory(models.Model):
    _name = 'project.category'
    _description = 'Project Category'

    name = fields.Char(string="Category Name", required=True)
    description = fields.Text(string="Description")


class ProjectProgram(models.Model):
    _name = 'project.program'
    _description = 'Project Program'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Program Name", required=True, tracking=True)
    description = fields.Text(string="Description")
    manager_id = fields.Many2one('hr.employee', string="Program Manager", tracking=True)
    project_ids = fields.One2many('project.project', 'program_id', string="Projects")


class ProjectPhase(models.Model):
    _name = 'project.phase'
    _description = 'Project Phase'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Phase Name", required=True, tracking=True)
    project_id = fields.Many2one('project.project', string="Project", required=True, ondelete='cascade', tracking=True)
    start_date = fields.Date(string="Start Date", tracking=True)
    end_date = fields.Date(string="End Date", tracking=True)
    task_ids = fields.One2many('project.task', 'phase_id', string="Tasks")
    milestone_ids = fields.One2many('project.milestone', 'phase_id', string="Milestones")
    progress = fields.Float(string="Phase Progress (%)", compute="_compute_progress", store=True, tracking=True)

    @api.depends('milestone_ids.is_reached')
    def _compute_progress(self):
        for phase in self:
            total = len(phase.milestone_ids)
            if total > 0:
                reached = len(phase.milestone_ids.filtered(lambda m: m.is_reached))
                phase.progress = (reached / total) * 100
            else:
                phase.progress = 0.0

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for phase in self:
            if phase.start_date and phase.end_date and phase.start_date > phase.end_date:
                raise ValidationError("Phase Start Date cannot be after End Date.")

    @api.constrains('start_date', 'end_date', 'project_id')
    def _check_phase_dates_within_project(self):
        for phase in self:
            proj = phase.project_id
            if proj:
                if phase.start_date and (phase.start_date < proj.planned_start_date or phase.start_date > proj.planned_end_date):
                    raise ValidationError("Phase Start Date (%s) must be within Project timeline (%s to %s)." % (phase.start_date, proj.planned_start_date, proj.planned_end_date))
                if phase.end_date and (phase.end_date < proj.planned_start_date or phase.end_date > proj.planned_end_date):
                    raise ValidationError("Phase End Date (%s) must be within Project timeline (%s to %s)." % (phase.end_date, proj.planned_start_date, proj.planned_end_date))


class ProjectProject(models.Model):
    _inherit = 'project.project'

    # Make Manager required
    user_id = fields.Many2one(
        'res.users', 
        string='Project Manager', 
        required=True, 
        tracking=True, 
        default=lambda self: self.env.user
    )

    project_code = fields.Char(string="Project Code", readonly=True, copy=False, default="/", tracking=True)
    
    # Category converted to Model
    project_category_id = fields.Many2one('project.category', string="Project Category", required=True, tracking=True)
    
    # Sponsor made required
    project_sponsor_id = fields.Many2one('hr.employee', string="Project Sponsor", required=True, tracking=True)
    
    project_department_id = fields.Many2one('hr.department', string="Owning Department", tracking=True)
    planned_start_date = fields.Date(string="Planned Start Date", required=True, tracking=True)
    planned_end_date = fields.Date(string="Planned End Date", required=True, tracking=True)
    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High')
    ], string="Priority", default='medium', tracking=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('closed', 'Closed')
    ], string="Workflow State", default='draft', required=True, tracking=True, copy=False)

    submitted_by_id = fields.Many2one('res.users', string="Submitted By", readonly=True, copy=False, tracking=True)
    program_id = fields.Many2one('project.program', string="Program", tracking=True)
    project_division_id = fields.Many2one('hr.division', string="Division", tracking=True)
    phase_ids = fields.One2many('project.phase', 'project_id', string="Phases")
    
    # Progress rolled up from Phases instead of Milestones directly
    project_progress = fields.Float(string="Project Progress (%)", compute="_compute_project_progress", store=True, tracking=True)
    allow_task_dependencies = fields.Boolean(default=True)

    # Computed Dashboard Statistics
    overdue_tasks_count = fields.Integer(string="Overdue Tasks Count", compute="_compute_dashboard_stats")
    critical_issues_count = fields.Integer(string="Critical Issues Count", compute="_compute_dashboard_stats")
    open_risks_count = fields.Integer(string="Open Risks Count", compute="_compute_dashboard_stats")
    is_delayed = fields.Boolean(string="Is Delayed", compute="_compute_dashboard_stats")
    budget_status = fields.Selection([
        ('on_track', 'On Track'),
        ('exceeded', 'Budget Exceeded')
    ], string="Budget Status", compute="_compute_dashboard_stats")
    project_health = fields.Selection([
        ('green', 'On Track (Green)'),
        ('amber', 'At Risk (Amber)'),
        ('red', 'Critical (Red)')
    ], string="Project Health", compute="_compute_dashboard_stats")

    @api.depends('planned_end_date', 'project_progress', 'issue_ids.severity', 'issue_ids.state', 
                 'risk_ids.state', 'risk_ids.rating_level', 'task_ids.planned_end_date', 
                 'task_ids.task_status', 'budget_amount', 'actual_cost')
    def _compute_dashboard_stats(self):
        today = fields.Date.today()
        for project in self:
            # Overdue tasks
            overdue_tasks = project.task_ids.filtered(
                lambda t: t.planned_end_date and t.planned_end_date < today and t.task_status != 'completed'
            )
            project.overdue_tasks_count = len(overdue_tasks)

            # Critical issues
            crit_issues = project.issue_ids.filtered(
                lambda i: i.severity == 'critical' and i.state in ('draft', 'open')
            )
            project.critical_issues_count = len(crit_issues)

            # Open risks
            open_risks = project.risk_ids.filtered(lambda r: r.state == 'open')
            project.open_risks_count = len(open_risks)

            # High/critical risks
            high_risks = open_risks.filtered(lambda r: r.rating_level in ('high', 'critical'))

            # Delayed flag
            project.is_delayed = project.project_progress < 100.0 and project.planned_end_date and project.planned_end_date < today

            # Budget status
            if project.budget_amount > 0 and project.actual_cost > project.budget_amount:
                project.budget_status = 'exceeded'
            else:
                project.budget_status = 'on_track'

            # Project Health
            if project.critical_issues_count > 0 or len(high_risks) > 0 or project.budget_status == 'exceeded':
                project.project_health = 'red'
            elif project.is_delayed or project.open_risks_count > 0:
                project.project_health = 'amber'
            else:
                project.project_health = 'green'

    @api.depends('phase_ids.progress')
    def _compute_project_progress(self):
        for project in self:
            phases = project.phase_ids
            if phases:
                 project.project_progress = sum(phases.mapped('progress')) / len(phases)
            else:
                 project.project_progress = 0.0

    @api.constrains('planned_start_date', 'planned_end_date')
    def _check_planned_dates(self):
        for project in self:
            if project.planned_start_date and project.planned_end_date and project.planned_start_date > project.planned_end_date:
                raise ValidationError("Planned Start Date cannot be after Planned End Date.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('project_code') or vals.get('project_code') == '/':
                vals['project_code'] = self.env['ir.sequence'].next_by_code('project.project.code') or '/'
        return super(ProjectProject, self).create(vals_list)

    def write(self, vals):
        for project in self:
            if project.state in ['approved', 'active', 'closed']:
                # If editing state field only, skip Maker check
                if 'state' in vals and len(vals) == 1:
                    continue
                
                # Check edit criteria
                core_fields = ['name', 'planned_start_date', 'planned_end_date', 'project_sponsor_id', 
                               'project_department_id', 'project_category_id', 'priority', 'program_id']
                if any(f in vals for f in core_fields):
                    if not self.env.user.has_group('ahadu_project_management.group_pmo_admin'):
                        # Non-PMO Admin edits core fields: push back to draft
                        vals['state'] = 'draft'
                        project.message_post(body="Core metadata fields modified. Project state reset to Draft for re-approval.")
        return super(ProjectProject, self).write(vals)

    def action_submit(self):
        for project in self:
            if project.state != 'draft':
                raise UserError("Only draft projects can be submitted for approval.")
            project.write({
                'state': 'submitted',
                'submitted_by_id': self.env.user.id
            })

    def action_approve(self):
        for project in self:
            if project.state != 'submitted':
                raise UserError("Only submitted projects can be approved.")
            
            # Maker/Checker verification
            submitter = project.submitted_by_id or project.create_uid
            submitter_employee = self.env['hr.employee'].search([('user_id', '=', submitter.id)], limit=1)
            
            if submitter_employee and submitter_employee.parent_id:
                current_employee = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)], limit=1)
                if not current_employee or current_employee.id != submitter_employee.parent_id.id:
                    # Allow bypass for PMO Admin group
                    if not self.env.user.has_group('ahadu_project_management.group_pmo_admin'):
                        raise ValidationError("Maker-Checker Rule: Only the submitter's manager (%s) or a PMO Admin can approve this project." % submitter_employee.parent_id.name)
            else:
                # Fallback if no manager relationship is set
                if self.env.user == submitter and not self.env.user.has_group('ahadu_project_management.group_pmo_admin'):
                    raise ValidationError("Maker-Checker Rule: You cannot approve a project you submitted.")

            project.write({'state': 'approved'})

    def action_activate(self):
        for project in self:
            if project.state != 'approved':
                raise UserError("A project cannot become Active unless it has been Approved first.")
            project.write({'state': 'active'})

    def action_close(self):
        for project in self:
            if project.state != 'active':
                raise UserError("Only active projects can be closed.")
            project.write({'state': 'closed'})

    def action_reject(self):
        for project in self:
            if project.state != 'submitted':
                raise UserError("Only submitted projects can be rejected.")
            project.write({
                'state': 'draft',
                'submitted_by_id': False
            })

    @api.model
    def get_project_dashboard_data(self, filters=None):
        filters = filters or {}
        user = self.env.user
        employee = self.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)

        # 1. Determine User Role
        user_role = filters.get('active_role')
        if not user_role or user_role == 'auto':
            if user.has_group('ahadu_project_management.group_pmo_admin'):
                user_role = 'pmo'
            elif employee and employee.job_id:
                access = self.env['project.dashboard.access'].search([('job_id', '=', employee.job_id.id)], limit=1)
                user_role = access.dashboard_scope if access else 'executive'
            else:
                user_role = 'executive'

        # 2. Build 15-Filter Search Domain
        domain = []

        # Filter 1: Project
        if filters.get('project_id') and filters['project_id'] != 'all':
            domain.append(('id', '=', int(filters['project_id'])))

        # Filter 2: Program
        if filters.get('program_id') and filters['program_id'] != 'all':
            domain.append(('program_id', '=', int(filters['program_id'])))

        # Filter 3: Directorate (Department)
        if filters.get('department_id') and filters['department_id'] != 'all':
            domain.append(('project_department_id', '=', int(filters['department_id'])))

        # Filter 4: Division
        if filters.get('division_id') and filters['division_id'] != 'all':
            domain.append(('project_division_id', '=', int(filters['division_id'])))

        # Filter 5: Sponsor
        if filters.get('sponsor_id') and filters['sponsor_id'] != 'all':
            domain.append(('project_sponsor_id', '=', int(filters['sponsor_id'])))

        # Filter 6: PM
        if filters.get('pm_id') and filters['pm_id'] != 'all':
            domain.append(('user_id', '=', int(filters['pm_id'])))

        # Filter 7: Category
        if filters.get('category_id') and filters['category_id'] != 'all':
            domain.append(('project_category_id', '=', int(filters['category_id'])))

        # Filter 8: Status
        if filters.get('state') and filters['state'] != 'all':
            domain.append(('state', '=', filters['state']))

        # Filter 9: Priority
        if filters.get('priority') and filters['priority'] != 'all':
            domain.append(('priority', '=', filters['priority']))

        # Role-based Scoping
        if user_role == 'sponsor' and employee:
            domain.append(('project_sponsor_id', '=', employee.id))
        elif user_role == 'pm':
            domain.append(('user_id', '=', user.id))
        elif user_role == 'team':
            tasks = self.env['project.task'].search([('user_ids', 'in', [user.id])])
            domain.append(('id', 'in', tasks.mapped('project_id').ids or [0]))

        projects = self.search(domain)

        # Filter 10: Risk Level post-filter
        if filters.get('risk_level') and filters['risk_level'] != 'all':
            projects = projects.filtered(lambda p: any(r.rating_level == filters['risk_level'] for r in p.risk_ids))

        # Filter 13: Date Range
        if filters.get('date_from'):
            projects = projects.filtered(lambda p: p.planned_start_date and p.planned_start_date >= fields.Date.from_string(filters['date_from']))
        if filters.get('date_to'):
            projects = projects.filtered(lambda p: p.planned_end_date and p.planned_end_date <= fields.Date.from_string(filters['date_to']))

        # Filter 14: Budget Status
        if filters.get('budget_status') and filters['budget_status'] != 'all':
            projects = projects.filtered(lambda p: p.budget_status == filters['budget_status'])

        # Filter 15: Health post-filter
        if filters.get('health') and filters['health'] != 'all':
            projects = projects.filtered(lambda p: p.project_health == filters['health'])

        today = fields.Date.today()

        # 3. Dynamic Filter Options Payload
        all_projs = self.search([])
        divisions_data = []
        if 'hr.division' in self.env:
            try:
                divisions_data = self.env['hr.division'].search_read([], ['id', 'name'])
            except Exception:
                divisions_data = []
        filters_lookup = {
            'projects': self.search_read([], ['id', 'name']),
            'programs': self.env['project.program'].search_read([], ['id', 'name']),
            'departments': self.env['hr.department'].search_read([], ['id', 'name']),
            'divisions': divisions_data,
            'sponsors': self.env['hr.employee'].search_read([('id', 'in', all_projs.mapped('project_sponsor_id').ids)], ['id', 'name']),
            'pms': self.env['res.users'].search_read([('id', 'in', all_projs.mapped('user_id').ids)], ['id', 'name']),
            'categories': self.env['project.category'].search_read([], ['id', 'name']),
            'resources': self.env['hr.employee'].search_read([], ['id', 'name']),
        }

        # 4. Global Baseline KPIs
        total_projects = len(projects)
        active_projects = len(projects.filtered(lambda p: p.state == 'active'))
        completed_projects = len(projects.filtered(lambda p: p.state == 'closed'))
        on_track = len(projects.filtered(lambda p: p.project_health == 'green'))
        at_risk = len(projects.filtered(lambda p: p.project_health == 'amber'))
        critical = len(projects.filtered(lambda p: p.project_health == 'red'))

        total_budget = sum(projects.mapped('budget_amount'))
        total_actual_cost = sum(projects.mapped('actual_cost'))
        budget_variance = total_budget - total_actual_cost

        all_tasks = projects.mapped('task_ids')
        all_risks = projects.mapped('risk_ids')
        all_issues = projects.mapped('issue_ids')
        all_changes = self.env['project.change_request'].search([('project_id', 'in', projects.ids)])

        overdue_tasks = len(all_tasks.filtered(lambda t: t.planned_end_date and t.planned_end_date < today and t.task_status != 'completed'))
        open_risks = len(all_risks.filtered(lambda r: r.state == 'open'))
        critical_issues_count = len(all_issues.filtered(lambda i: i.severity == 'critical' and i.state in ('draft', 'open')))
        open_issues = len(all_issues.filtered(lambda i: i.state in ('draft', 'open')))
        pending_changes = len(all_changes.filtered(lambda c: c.state == 'submitted'))

        by_health = {'labels': ['On Track', 'At Risk', 'Critical'], 'data': [on_track, at_risk, critical]}

        dept_counts = {}
        for p in projects:
            d = p.project_department_id.name or 'Unassigned'
            dept_counts[d] = dept_counts.get(d, 0) + 1
        by_department = {'labels': list(dept_counts.keys()), 'data': list(dept_counts.values())}

        div_counts = {}
        for p in projects:
            d = p.project_division_id.name or 'Unassigned'
            div_counts[d] = div_counts.get(d, 0) + 1
        by_division = {'labels': list(div_counts.keys()), 'data': list(div_counts.values())}

        sponsor_counts = {}
        for p in projects:
            s = p.project_sponsor_id.name or 'Unassigned'
            sponsor_counts[s] = sponsor_counts.get(s, 0) + 1
        by_sponsor = {'labels': list(sponsor_counts.keys()), 'data': list(sponsor_counts.values())}

        # Extended data processing for comprehensive dashboards
        cat_counts = {}
        for p in projects:
            c = p.project_category_id.name or 'Unassigned'
            cat_counts[c] = cat_counts.get(c, 0) + 1
        by_category = {'labels': list(cat_counts.keys()), 'data': list(cat_counts.values())}

        budget_by_dept_labels = list(dept_counts.keys())
        budget_by_dept_chart = {
            'labels': budget_by_dept_labels,
            'planned': [sum(projects.filtered(
                lambda p, d=d: (p.project_department_id.name or 'Unassigned') == d
            ).mapped('budget_amount')) for d in budget_by_dept_labels],
            'actual': [sum(projects.filtered(
                lambda p, d=d: (p.project_department_id.name or 'Unassigned') == d
            ).mapped('actual_cost')) for d in budget_by_dept_labels],
        }

        budget_variance_chart = {
            'labels': [p.name[:20] for p in projects[:10]],
            'data': [p.budget_variance for p in projects[:10]],
        }

        # Risk by level
        risk_levels = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
        for r in all_risks.filtered(lambda r: r.state == 'open'):
            lvl = r.rating_level or 'low'
            if lvl in risk_levels:
                risk_levels[lvl] += 1
        risk_by_level_chart = {
            'labels': ['Critical', 'High', 'Medium', 'Low'],
            'data': [risk_levels['critical'], risk_levels['high'], risk_levels['medium'], risk_levels['low']],
        }

        # Task status chart
        task_statuses = {}
        for t in all_tasks:
            s = t.task_status or 'not_started'
            task_statuses[s] = task_statuses.get(s, 0) + 1
        task_status_chart = {'labels': list(task_statuses.keys()), 'data': list(task_statuses.values())}

        # Schedule performance by project
        sched_labels = [p.name[:15] for p in projects[:8]]
        sched_data = []
        for p in projects[:8]:
            total_p = len(p.task_ids)
            done_p = len(p.task_ids.filtered(lambda t: t.task_status in ('in_progress', 'completed')))
            sched_data.append(round((done_p / total_p * 100) if total_p else 0, 1))
        schedule_perf_chart = {'labels': sched_labels, 'data': sched_data}

        # WBS progress by project
        wbs_chart = {
            'labels': [p.name[:15] for p in projects[:8]],
            'data': [round(p.project_progress, 1) for p in projects[:8]],
        }

        # Milestone progress chart
        milestones_sample = self.env['project.milestone'].search(
            [('project_id', 'in', projects.ids)], limit=8)
        milestone_chart = {
            'labels': [m.name[:15] for m in milestones_sample],
            'data': [100 if m.is_reached else 0 for m in milestones_sample],
        }

        # Timesheet hours by weekday (current user)
        from datetime import timedelta
        week_start = today - timedelta(days=today.weekday())
        timesheet_lines = self.env['account.analytic.line'].search([
            ('employee_id', '=', employee.id if employee else 0),
            ('date', '>=', week_start), ('date', '<=', today),
        ])
        weekday_hrs = {i: 0.0 for i in range(7)}
        for line in timesheet_lines:
            if line.date:
                weekday_hrs[line.date.weekday()] += line.unit_amount
        timesheet_chart = {
            'labels': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            'data': [round(weekday_hrs[i], 1) for i in range(7)],
        }
        timesheet_hours_week = round(sum(timesheet_lines.mapped('unit_amount')), 1)

        # Delayed projects
        delayed_projects_qs = projects.filtered(
            lambda p: p.planned_end_date and p.planned_end_date < today and p.state in ('active', 'approved'))

        # Delayed projects count
        delayed_count = len(delayed_projects_qs)

        # Programs count
        programs_count = self.env['project.program'].search_count([])

        # WBS completion avg
        wbs_completion = round(
            sum(p.project_progress for p in projects) / total_projects if total_projects else 0, 1)

        # Schedule performance index
        schedule_performance = round(
            (on_track / total_projects * 100) if total_projects else 100.0, 1)

        # Resource utilization
        assigned_emp_ids = set()
        for t in all_tasks.filtered(lambda t: t.task_status not in ('completed', 'cancelled')):
            for emp in t.user_ids.mapped('employee_id'):
                assigned_emp_ids.add(emp.id)
        total_employees = self.env['hr.employee'].search_count([('active', '=', True)])
        resource_utilization = round(
            (len(assigned_emp_ids) / total_employees * 100) if total_employees else 0, 1)

        # Compliance rate
        compliance_rate = round(
            ((on_track + at_risk) / total_projects * 100) if total_projects else 100.0, 1)

        # Team member specific
        user_tasks = all_tasks.filtered(lambda t: user.id in t.user_ids.ids)
        my_completed_tasks = len(user_tasks.filtered(lambda t: t.task_status == 'completed'))
        my_projects_count = len(user_tasks.mapped('project_id'))

        # My task status chart (for team role)
        my_task_statuses = {}
        for t in user_tasks:
            s = t.task_status or 'not_started'
            my_task_statuses[s] = my_task_statuses.get(s, 0) + 1
        my_task_status_chart = {'labels': list(my_task_statuses.keys()), 'data': list(my_task_statuses.values())}

        # Tables
        pending_approvals_list = []
        for p in projects.filtered(lambda pr: pr.state == 'submitted'):
            pending_approvals_list.append({
                'id': p.id, 'name': p.name, 'code': p.project_code,
                'sponsor': p.project_sponsor_id.name or '',
                'pm': p.user_id.name or '',
                'type': 'Project Onboarding',
                'date': p.create_date.strftime('%Y-%m-%d') if p.create_date else '',
            })
        for c in all_changes.filtered(lambda ch: ch.state == 'submitted'):
            pending_approvals_list.append({
                'id': c.project_id.id if c.project_id else 0,
                'name': c.name,
                'code': '',
                'sponsor': c.project_id.project_sponsor_id.name if c.project_id and c.project_id.project_sponsor_id else '',
                'pm': c.project_id.user_id.name if c.project_id and c.project_id.user_id else '',
                'type': 'Change Request',
                'date': c.create_date.strftime('%Y-%m-%d') if c.create_date else '',
            })

        strategic_milestones_list = []
        milestones = self.env['project.milestone'].search(
            [('project_id', 'in', projects.ids)], limit=10, order='deadline asc')
        for m in milestones:
            strategic_milestones_list.append({
                'id': m.id, 'name': m.name, 'project': m.project_id.name,
                'deadline': m.deadline.strftime('%Y-%m-%d') if m.deadline else '',
                'is_reached': m.is_reached,
            })

        high_risk_list = []
        for r in all_risks.filtered(lambda ri: ri.rating_level in ('high', 'critical') and ri.state == 'open'):
            high_risk_list.append({
                'id': r.id, 'name': r.name, 'project': r.project_id.name,
                'rating': (r.rating_level or 'high').upper(),
                'owner': r.owner_id.name if r.owner_id else 'Unassigned',
            })

        critical_issues_list = []
        for i in all_issues.filtered(lambda is_: is_.severity == 'critical' and is_.state in ('draft', 'open')):
            critical_issues_list.append({
                'id': i.id, 'name': i.name, 'project': i.project_id.name,
                'severity': (i.severity or 'critical').upper(),
                'assigned_to': i.owner_id.name if i.owner_id else 'Unassigned',
            })

        my_tasks_list = []
        for t in user_tasks[:20]:
            my_tasks_list.append({
                'id': t.id, 'name': t.name, 'project': t.project_id.name,
                'priority': t.priority,
                'deadline': t.planned_end_date.strftime('%Y-%m-%d') if t.planned_end_date else '',
                'progress': round(t.completion_percentage, 0),
                'status': t.task_status or 'not_started',
            })

        delayed_list = []
        for p in delayed_projects_qs[:15]:
            delayed_list.append({
                'id': p.id, 'name': p.name,
                'pm': p.user_id.name or '',
                'end_date': p.planned_end_date.strftime('%Y-%m-%d') if p.planned_end_date else '',
                'health': p.project_health or 'red',
            })

        project_list = []
        for p in projects[:20]:
            project_list.append({
                'id': p.id, 'name': p.name,
                'pm': p.user_id.name or '',
                'state': p.state,
                'progress': round(p.project_progress, 0),
                'budget': '{:,.0f} ETB'.format(p.budget_amount) if p.budget_amount else '0 ETB',
                'actual': '{:,.0f} ETB'.format(p.actual_cost) if p.actual_cost else '0 ETB',
                'health': p.project_health or '',
            })

        change_requests_list = []
        for c in all_changes.filtered(lambda ch: ch.state == 'submitted')[:15]:
            change_requests_list.append({
                'id': c.id, 'name': c.name,
                'project': c.project_id.name if c.project_id else '',
                'type': c.change_type_id.name if c.change_type_id else 'General',
                'date': c.create_date.strftime('%Y-%m-%d') if c.create_date else '',
            })

        is_pmo_admin = user.has_group('ahadu_project_management.group_pmo_admin')

        return {
            'user_role': user_role,
            'is_pmo_admin': is_pmo_admin,
            'filters_lookup': filters_lookup,
            'kpis': {
                'total_projects': total_projects,
                'active_projects': active_projects,
                'completed_projects': completed_projects,
                'on_track': on_track,
                'at_risk': at_risk,
                'critical': critical,
                'total_budget': total_budget,
                'total_actual_cost': total_actual_cost,
                'budget_variance': budget_variance,
                'overdue_tasks': overdue_tasks,
                'open_risks': open_risks,
                'critical_issues': critical_issues_count,
                'open_issues': open_issues,
                'pending_changes': pending_changes,
                'success_rate': round((completed_projects / total_projects * 100), 1) if total_projects > 0 else 0.0,
                'delayed_projects': delayed_count,
                'resource_utilization': resource_utilization,
                'schedule_performance': schedule_performance,
                'programs_count': programs_count,
                'compliance_rate': compliance_rate,
                'wbs_completion': wbs_completion,
                'my_completed_tasks': my_completed_tasks,
                'my_projects': my_projects_count,
                'timesheet_hours': timesheet_hours_week,
            },
            'charts': {
                'by_health': by_health,
                'by_department': by_department,
                'by_division': by_division,
                'by_sponsor': by_sponsor,
                'by_category': by_category,
                'budget_by_dept': budget_by_dept_chart,
                'budget_variance': budget_variance_chart,
                'risk_by_level': risk_by_level_chart,
                'task_status': my_task_status_chart if user_role == 'team' else task_status_chart,
                'schedule_performance': schedule_perf_chart,
                'wbs_progress': wbs_chart,
                'milestone_progress': milestone_chart,
                'timesheet_hours': timesheet_chart,
            },
            'tables': {
                'pending_approvals': pending_approvals_list,
                'strategic_milestones': strategic_milestones_list,
                'high_risks': high_risk_list,
                'critical_issues': critical_issues_list,
                'my_tasks': my_tasks_list,
                'delayed_projects': delayed_list,
                'project_list': project_list,
                'change_requests': change_requests_list,
            },
        }


class ProjectMilestone(models.Model):
    _inherit = 'project.milestone'

    phase_id = fields.Many2one('project.phase', string="Phase", tracking=True)
    task_ids = fields.One2many('project.task', 'milestone_id', string="Tasks")
    
    # Milestone completed automatically if all tasks are complete
    is_reached = fields.Boolean(
        string="Is Reached",
        compute="_compute_is_reached",
        store=True,
        readonly=False,
        tracking=True
    )

    @api.depends('task_ids.task_status')
    def _compute_is_reached(self):
        for milestone in self:
            tasks = milestone.task_ids
            if tasks:
                milestone.is_reached = all(t.task_status == 'completed' for t in tasks)

    @api.constrains('deadline', 'project_id')
    def _check_milestone_deadline_within_project(self):
        for milestone in self:
            proj = milestone.project_id
            if proj and milestone.deadline:
                if milestone.deadline < proj.planned_start_date or milestone.deadline > proj.planned_end_date:
                    raise ValidationError("Milestone Deadline (%s) must be within Project timeline (%s to %s)." % (milestone.deadline, proj.planned_start_date, proj.planned_end_date))
