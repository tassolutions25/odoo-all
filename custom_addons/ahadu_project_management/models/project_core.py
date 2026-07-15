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
    phase_ids = fields.One2many('project.phase', 'project_id', string="Phases")
    
    # Progress rolled up from Phases instead of Milestones directly
    project_progress = fields.Float(string="Project Progress (%)", compute="_compute_project_progress", store=True, tracking=True)
    allow_task_dependencies = fields.Boolean(default=True)

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
