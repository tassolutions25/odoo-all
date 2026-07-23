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
        domain = []

        if filters.get('state') and filters['state'] != 'all':
            domain.append(('state', '=', filters['state']))
        if filters.get('department') and filters['department'] != 'all':
            domain.append(('project_department_id', '=', int(filters['department'])))
        if filters.get('priority') and filters['priority'] != 'all':
            domain.append(('priority', '=', filters['priority']))

        projects = self.search(domain)

        if filters.get('health') and filters['health'] != 'all':
            projects = projects.filtered(lambda p: p.project_health == filters['health'])

        total_projects = len(projects)
        active_projects = len(projects.filtered(lambda p: p.state == 'active'))
        completed_projects = len(projects.filtered(lambda p: p.state == 'closed'))
        on_track = len(projects.filtered(lambda p: p.project_health == 'green'))
        at_risk = len(projects.filtered(lambda p: p.project_health == 'amber'))
        critical = len(projects.filtered(lambda p: p.project_health == 'red'))

        total_budget = sum(projects.mapped('budget_amount'))
        total_actual_cost = sum(projects.mapped('actual_cost'))
        budget_variance = total_budget - total_actual_cost

        open_risks = sum(projects.mapped('open_risks_count'))
        open_issues = sum(projects.mapped('critical_issues_count'))
        overdue_tasks = sum(projects.mapped('overdue_tasks_count'))

        by_health = {
            'labels': ['On Track', 'At Risk', 'Critical'],
            'data': [on_track, at_risk, critical]
        }

        states_count = {}
        for p in projects:
            st = dict(self._fields['state'].selection).get(p.state, p.state)
            states_count[st] = states_count.get(st, 0) + 1
        by_state = {
            'labels': list(states_count.keys()),
            'data': list(states_count.values())
        }

        depts_count = {}
        for p in projects:
            dept = p.project_department_id.name or 'Unassigned'
            depts_count[dept] = depts_count.get(dept, 0) + 1
        by_department = {
            'labels': list(depts_count.keys()),
            'data': list(depts_count.values())
        }

        prio_count = {}
        for p in projects:
            pr = dict(self._fields['priority'].selection).get(p.priority, p.priority)
            prio_count[pr] = prio_count.get(pr, 0) + 1
        by_priority = {
            'labels': list(prio_count.keys()),
            'data': list(prio_count.values())
        }

        dept_budget = {}
        for p in projects:
            dept = p.project_department_id.name or 'Unassigned'
            if dept not in dept_budget:
                dept_budget[dept] = {'planned': 0.0, 'actual': 0.0}
            dept_budget[dept]['planned'] += p.budget_amount
            dept_budget[dept]['actual'] += p.actual_cost

        budget_by_dept = {
            'labels': list(dept_budget.keys()),
            'planned': [v['planned'] for v in dept_budget.values()],
            'actual': [v['actual'] for v in dept_budget.values()]
        }

        var_labels = [p.name for p in projects[:10]]
        var_data = [p.budget_variance for p in projects[:10]]
        budget_variance_chart = {
            'labels': var_labels,
            'data': var_data
        }

        all_risks = projects.mapped('risk_ids').filtered(lambda r: r.state == 'open')
        risk_levels = {}
        for r in all_risks:
            lvl = (r.rating_level or 'low').capitalize()
            risk_levels[lvl] = risk_levels.get(lvl, 0) + 1
        risk_by_level = {
            'labels': list(risk_levels.keys()) or ['Low'],
            'data': list(risk_levels.values()) or [0]
        }

        all_issues = projects.mapped('issue_ids').filtered(lambda i: i.state in ('draft', 'open'))
        issue_sevs = {}
        for i in all_issues:
            sev = (i.severity or 'low').capitalize()
            issue_sevs[sev] = issue_sevs.get(sev, 0) + 1
        issues_by_severity = {
            'labels': list(issue_sevs.keys()) or ['Low'],
            'data': list(issue_sevs.values()) or [0]
        }

        all_tasks = projects.mapped('task_ids')
        task_stats = {'Completed': 0, 'In Progress': 0, 'Overdue': 0, 'Not Started': 0}
        today = fields.Date.today()
        for t in all_tasks:
            if t.task_status == 'completed':
                task_stats['Completed'] += 1
            elif t.planned_end_date and t.planned_end_date < today:
                task_stats['Overdue'] += 1
            elif t.task_status == 'in_progress':
                task_stats['In Progress'] += 1
            else:
                task_stats['Not Started'] += 1
        task_completion = {
            'labels': list(task_stats.keys()),
            'data': list(task_stats.values())
        }

        bins = {'0-25%': 0, '26-50%': 0, '51-75%': 0, '76-100%': 0}
        for p in projects:
            if p.project_progress <= 25:
                bins['0-25%'] += 1
            elif p.project_progress <= 50:
                bins['26-50%'] += 1
            elif p.project_progress <= 75:
                bins['51-75%'] += 1
            else:
                bins['76-100%'] += 1
        progress_distribution = {
            'labels': list(bins.keys()),
            'data': list(bins.values())
        }

        on_time = len(projects.filtered(lambda p: not p.is_delayed and p.project_health == 'green'))
        delayed = len(projects.filtered(lambda p: p.is_delayed))
        at_risk_time = len(projects.filtered(lambda p: not p.is_delayed and p.project_health != 'green'))
        timeline_status = {
            'labels': ['On Time', 'Delayed', 'At Risk'],
            'data': [on_time, delayed, at_risk_time]
        }

        departments = self.env['hr.department'].search_read([], ['id', 'name'])

        return {
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
                'open_risks': open_risks,
                'open_issues': open_issues,
                'overdue_tasks': overdue_tasks,
            },
            'charts': {
                'by_health': by_health,
                'by_state': by_state,
                'by_department': by_department,
                'by_priority': by_priority,
                'budget_by_dept': budget_by_dept,
                'budget_variance': budget_variance_chart,
                'risk_by_level': risk_by_level,
                'issues_by_severity': issues_by_severity,
                'task_completion': task_completion,
                'progress_distribution': progress_distribution,
                'timeline_status': timeline_status,
            },
            'filters': {
                'departments': departments,
            }
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
