from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

class ProjectBudgetCategory(models.Model):
    _name = 'project.budget.category'
    _description = 'Project Budget Category'

    name = fields.Char(string="Category Name", required=True)
    description = fields.Text(string="Description")


class ProjectBudget(models.Model):
    _name = 'project.budget'
    _description = 'Project Budget'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string="Budget Title", required=True, default="New Budget", tracking=True)
    project_id = fields.Many2one('project.project', string="Project", required=True, tracking=True)
    currency_id = fields.Many2one('res.currency', string="Currency", default=lambda self: self.env.company.currency_id, required=True)
    
    line_ids = fields.One2many('project.budget.line', 'budget_id', string="Budget Lines", copy=True)
    
    planned_amount = fields.Float(string="Planned Amount", compute="_compute_totals", store=True, tracking=True)
    actual_amount = fields.Float(string="Actual Cost", compute="_compute_totals", store=True, tracking=True)
    variance = fields.Float(string="Variance", compute="_compute_totals", store=True, tracking=True)
    utilization_rate = fields.Float(string="Utilization Rate (%)", compute="_compute_totals", store=True, tracking=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string="Budget State", default='draft', required=True, tracking=True, copy=False)
    
    submitted_by_id = fields.Many2one('res.users', string="Submitted By", readonly=True, copy=False)
    approved_by_id = fields.Many2one('res.users', string="Approved By", readonly=True, copy=False)
    description = fields.Text(string="Description")

    @api.depends('line_ids.planned_amount', 'line_ids.actual_amount')
    def _compute_totals(self):
        for budget in self:
            planned = sum(budget.line_ids.mapped('planned_amount'))
            actual = sum(budget.line_ids.mapped('actual_amount'))
            budget.planned_amount = planned
            budget.actual_amount = actual
            budget.variance = planned - actual
            budget.utilization_rate = (actual / planned * 100) if planned > 0 else 0.0

    @api.constrains('project_id', 'state')
    def _check_single_approved_budget(self):
        for budget in self:
            if budget.state == 'approved':
                # Ensure only one approved budget exists per project
                existing = self.search([
                    ('project_id', '=', budget.project_id.id),
                    ('state', '=', 'approved'),
                    ('id', '!=', budget.id)
                ])
                if existing:
                    raise ValidationError("Security Rule: An approved budget already exists for project '%s'. Reject/revise the old budget first before approving a new one." % budget.project_id.name)

    def action_submit(self):
        for budget in self:
            if budget.state != 'draft':
                raise UserError("Only draft budgets can be submitted.")
            budget.write({
                'state': 'submitted',
                'submitted_by_id': self.env.user.id
            })

    def action_approve(self):
        for budget in self:
            if budget.state != 'submitted':
                raise UserError("Only submitted budgets can be approved.")
            
            # Maker-Checker Rule
            submitter = budget.submitted_by_id or budget.create_uid
            if self.env.user == submitter and not self.env.user.has_group('ahadu_project_management.group_pmo_admin'):
                raise ValidationError("Maker-Checker Rule: You cannot approve a budget you submitted.")
            
            # Verify if user is project sponsor or PMO Admin
            is_sponsor = budget.project_id.project_sponsor_id.user_id == self.env.user
            is_pmo = self.env.user.has_group('ahadu_project_management.group_pmo_admin')
            if not (is_sponsor or is_pmo):
                raise ValidationError("Access Denied: Only the Project Sponsor (%s) or a PMO Administrator can approve this budget." % budget.project_id.project_sponsor_id.name)
            
            budget.write({
                'state': 'approved',
                'approved_by_id': self.env.user.id
            })
            # Log approval comment
            budget.message_post(body="Budget approved by %s." % self.env.user.name)

    def action_reject(self):
        for budget in self:
            if budget.state != 'submitted':
                raise UserError("Only submitted budgets can be rejected.")
            budget.write({
                'state': 'rejected'
            })
            budget.message_post(body="Budget rejected by %s." % self.env.user.name)

    def action_draft(self):
        for budget in self:
            if budget.state not in ['submitted', 'rejected']:
                raise UserError("Only submitted or rejected budgets can be set to draft.")
            budget.write({
                'state': 'draft',
                'submitted_by_id': False,
                'approved_by_id': False
            })


class ProjectBudgetLine(models.Model):
    _name = 'project.budget.line'
    _description = 'Project Budget Line'

    budget_id = fields.Many2one('project.budget', string="Budget Reference", required=True, ondelete='cascade')
    category_id = fields.Many2one('project.budget.category', string="Budget Category", required=True)
    currency_id = fields.Many2one('res.currency', related='budget_id.currency_id', store=True)
    
    planned_amount = fields.Float(string="Planned Amount", required=True)
    actual_amount = fields.Float(string="Actual Cost", compute="_compute_actual_amount", store=True)
    variance = fields.Float(string="Variance", compute="_compute_line_totals", store=True)
    utilization_rate = fields.Float(string="Utilization (%)", compute="_compute_line_totals", store=True)

    @api.depends('planned_amount', 'actual_amount')
    def _compute_line_totals(self):
        for line in self:
            line.variance = line.planned_amount - line.actual_amount
            line.utilization_rate = (line.actual_amount / line.planned_amount * 100) if line.planned_amount > 0 else 0.0

    @api.depends('budget_id.project_id.expense_ids.amount', 'budget_id.project_id.expense_ids.state', 'budget_id.project_id.expense_ids.category_id', 'category_id')
    def _compute_actual_amount(self):
        for line in self:
            project = line.budget_id.project_id
            if project and line.category_id:
                # Sum only approved expenses for this project and category
                expenses = project.expense_ids.filtered(
                    lambda e: e.category_id.id == line.category_id.id and e.state == 'approved'
                )
                line.actual_amount = sum(expenses.mapped('amount'))
            else:
                line.actual_amount = 0.0


class ProjectExpense(models.Model):
    _name = 'project.expense'
    _description = 'Project Expense'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string="Reference/Invoice", required=True, copy=False, default="/", tracking=True)
    date = fields.Date(string="Expense Date", default=fields.Date.today, required=True, tracking=True)
    project_id = fields.Many2one('project.project', string="Project", required=True, tracking=True)
    category_id = fields.Many2one('project.budget.category', string="Budget Category", required=True, tracking=True)
    currency_id = fields.Many2one('res.currency', string="Currency", default=lambda self: self.env.company.currency_id, required=True)
    amount = fields.Float(string="Amount", required=True, tracking=True)
    description = fields.Text(string="Description")
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string="Status", default='draft', required=True, tracking=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('project.expense.seq') or '/'
        return super(ProjectExpense, self).create(vals_list)

    def action_approve(self):
        for expense in self:
            # Check permissions: Project Manager or PMO Admin
            if not (self.env.user.has_group('ahadu_project_management.group_project_manager') or self.env.user.has_group('ahadu_project_management.group_pmo_admin')):
                raise ValidationError("Access Denied: Only a Project Manager or PMO Admin can approve expenses.")
            
            # Maker checker verification
            if expense.create_uid == self.env.user and not self.env.user.has_group('ahadu_project_management.group_pmo_admin'):
                raise ValidationError("Maker-Checker Rule: You cannot approve an expense you registered.")
            
            expense.write({'state': 'approved'})
            expense.message_post(body="Expense approved.")

    def action_reject(self):
        for expense in self:
            expense.write({'state': 'rejected'})
            expense.message_post(body="Expense rejected.")

    def action_draft(self):
        for expense in self:
            expense.write({'state': 'draft'})


class ProjectProject(models.Model):
    _inherit = 'project.project'

    budget_ids = fields.One2many('project.budget', 'project_id', string="Budgets")
    expense_ids = fields.One2many('project.expense', 'project_id', string="Expenses")
    
    active_budget_id = fields.Many2one('project.budget', string="Active Budget", compute="_compute_active_budget", store=True)
    budget_amount = fields.Float(string="Project Budget", compute="_compute_project_budget_totals", store=True, tracking=True)
    actual_cost = fields.Float(string="Actual Project Cost", compute="_compute_project_budget_totals", store=True, tracking=True)
    budget_variance = fields.Float(string="Budget Variance", compute="_compute_project_budget_totals", store=True, tracking=True)

    @api.depends('budget_ids.state')
    def _compute_active_budget(self):
        for proj in self:
            approved_budgets = proj.budget_ids.filtered(lambda b: b.state == 'approved')
            proj.active_budget_id = approved_budgets[0] if approved_budgets else False

    @api.depends('active_budget_id.planned_amount', 'active_budget_id.actual_amount')
    def _compute_project_budget_totals(self):
        for proj in self:
            budget = proj.active_budget_id
            if budget:
                proj.budget_amount = budget.planned_amount
                proj.actual_cost = budget.actual_amount
                proj.budget_variance = budget.variance
            else:
                proj.budget_amount = 0.0
                proj.actual_cost = 0.0
                proj.budget_variance = 0.0
