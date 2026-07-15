from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import datetime

class ProjectRisk(models.Model):
    _name = 'project.risk'
    _description = 'Project Risk'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'rating desc, id desc'

    project_id = fields.Many2one('project.project', string="Project", required=True, tracking=True)
    name = fields.Char(string="Risk Description/Title", required=True, tracking=True)
    
    probability = fields.Selection([
        ('1', 'Rare (1)'),
        ('2', 'Unlikely (2)'),
        ('3', 'Moderate (3)'),
        ('4', 'Likely (4)'),
        ('5', 'Almost Certain (5)')
    ], string="Probability", default='3', required=True, tracking=True)
    
    impact = fields.Selection([
        ('1', 'Insignificant (1)'),
        ('2', 'Minor (2)'),
        ('3', 'Moderate (3)'),
        ('4', 'Major (4)'),
        ('5', 'Catastrophic (5)')
    ], string="Impact", default='3', required=True, tracking=True)
    
    rating = fields.Integer(string="Risk Rating", compute="_compute_rating", store=True, tracking=True)
    rating_level = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string="Risk Level", compute="_compute_rating", store=True, tracking=True)
    
    mitigation_plan = fields.Text(string="Mitigation Plan", tracking=True)
    owner_id = fields.Many2one('hr.employee', string="Risk Owner", required=True, tracking=True)
    
    state = fields.Selection([
        ('open', 'Open'),
        ('mitigated', 'Mitigated'),
        ('closed', 'Closed')
    ], string="Status", default='open', required=True, tracking=True)
    
    escalation_triggered = fields.Boolean(string="Escalated Automatically", default=False, readonly=True)

    @api.depends('probability', 'impact')
    def _compute_rating(self):
        for risk in self:
            p = int(risk.probability or 0)
            i = int(risk.impact or 0)
            rating = p * i
            risk.rating = rating
            if rating <= 4:
                risk.rating_level = 'low'
            elif rating <= 10:
                risk.rating_level = 'medium'
            elif rating <= 16:
                risk.rating_level = 'high'
            else:
                risk.rating_level = 'critical'

    @api.constrains('owner_id')
    def _check_owner(self):
        for risk in self:
            if not risk.owner_id:
                raise ValidationError("Every risk must have an assigned owner.")

    def action_escalate(self):
        self.ensure_one()
        # Escalate high/critical risks to Sponsor and PMO Admin
        sponsor = self.project_id.project_sponsor_id
        pmo_group = self.env.ref('ahadu_project_management.group_pmo_admin', raise_if_not_found=False)
        recipients = self.env['res.partner']
        if sponsor and sponsor.user_id and sponsor.user_id.partner_id:
            recipients |= sponsor.user_id.partner_id
        if pmo_group:
            recipients |= pmo_group.users.mapped('partner_id')
        
        recipients = recipients.filtered(lambda p: p.email)
        if recipients:
            subject = "High Risk Escalation Alert: %s" % self.name
            body_html = """
                <p>Dear Stakeholder,</p>
                <p>The following project risk has been <strong>escalated</strong>:</p>
                <ul>
                    <li><strong>Project:</strong> %s</li>
                    <li><strong>Risk:</strong> %s</li>
                    <li><strong>Rating:</strong> %s (%s)</li>
                    <li><strong>Owner:</strong> %s</li>
                </ul>
                <p>Please review and confirm mitigation plans are in progress.</p>
            """ % (self.project_id.name, self.name, self.rating, dict(self._fields['rating_level'].selection).get(self.rating_level, self.rating_level), self.owner_id.name)
            
            mail_server = self.env['ir.mail_server'].search([], limit=1)
            email_from = mail_server.smtp_user if mail_server else 'noreply@ahadu.bank'
            
            for partner in recipients:
                self.env['mail.mail'].sudo().create({
                    'subject': subject,
                    'email_from': email_from,
                    'email_to': partner.email,
                    'body_html': body_html,
                    'auto_delete': True,
                }).send()

            self.message_post(body="High risk auto-escalated to Sponsor and PMO Admins. Email alerts sent.")
            self.write({'escalation_triggered': True})

    def action_mitigate(self):
        for risk in self:
            if risk.state != 'open':
                raise UserError("Only open risks can be marked as mitigated.")
            risk.write({'state': 'mitigated'})
            risk.message_post(body="Risk status updated to Mitigated.")

    def action_close_risk(self):
        for risk in self:
            if risk.state not in ['open', 'mitigated']:
                raise UserError("Only open or mitigated risks can be closed.")
            risk.write({'state': 'closed'})
            risk.message_post(body="Risk closed and archived for audit purposes.")

    def action_reopen(self):
        for risk in self:
            if risk.state not in ['mitigated', 'closed']:
                raise UserError("Only mitigated or closed risks can be reopened.")
            risk.write({'state': 'open'})
            risk.message_post(body="Risk reopened for re-assessment.")


class ProjectIssue(models.Model):
    _name = 'project.issue'
    _description = 'Project Issue'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'severity desc, date_identified desc'

    project_id = fields.Many2one('project.project', string="Project", required=True, tracking=True)
    name = fields.Char(string="Issue Title", required=True, tracking=True)
    description = fields.Text(string="Description", tracking=True)
    owner_id = fields.Many2one('hr.employee', string="Issue Owner", required=True, tracking=True)
    
    severity = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string="Severity", default='medium', required=True, tracking=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed')
    ], string="Status", default='draft', required=True, tracking=True)
    
    date_identified = fields.Date(string="Date Identified", default=fields.Date.today, required=True, tracking=True)
    date_resolved = fields.Date(string="Date Resolved", tracking=True)
    
    escalated = fields.Boolean(string="Is Escalated", default=False, tracking=True, copy=False)
    escalated_to_id = fields.Many2one('res.users', string="Escalated To", readonly=True, copy=False)
    escalation_date = fields.Date(string="Escalation Date", readonly=True, copy=False)

    @api.constrains('owner_id')
    def _check_owner(self):
        for issue in self:
            if not issue.owner_id:
                raise ValidationError("Every issue must have a responsible owner assigned.")

    def action_open(self):
        for issue in self:
            if issue.state != 'draft':
                raise UserError("Only draft issues can be marked as Open.")
            issue.write({'state': 'open'})
            if issue.severity == 'critical':
                # Critical issues escalated immediately
                issue.action_escalate()

    def action_resolve(self):
        for issue in self:
            if issue.state != 'open':
                raise UserError("Only open issues can be resolved.")
            issue.write({
                'state': 'resolved',
                'date_resolved': fields.Date.today()
            })
            issue.message_post(body="Issue marked as Resolved.")

    def action_close(self):
        for issue in self:
            if issue.state != 'resolved':
                raise UserError("Issues must be marked as Resolved before they can be Closed.")
            issue.write({'state': 'closed'})
            issue.message_post(body="Issue closed successfully.")

    def action_reopen_issue(self):
        for issue in self:
            if issue.state not in ['resolved', 'closed']:
                raise UserError("Only resolved or closed issues can be reopened.")
            issue.write({'state': 'open', 'date_resolved': False})
            issue.message_post(body="Issue reopened for further investigation.")

    def action_escalate(self):
        for issue in self:
            sponsor_user = issue.project_id.project_sponsor_id.user_id
            if not sponsor_user:
                sponsor_user = self.env.ref('ahadu_project_management.group_pmo_admin').users[:1]
            
            issue.write({
                'escalated': True,
                'escalated_to_id': sponsor_user.id,
                'escalation_date': fields.Date.today()
            })
            issue._send_escalation_email(sponsor_user)

    def _send_escalation_email(self, sponsor_user):
        self.ensure_one()
        if not sponsor_user.partner_id or not sponsor_user.partner_id.email:
            return
        
        subject = "CRITICAL ISSUE ESCALATION: Project %s" % (self.project_id.name)
        body_html = """
            <p>Dear Project Sponsor,</p>
            <p>The following critical issue has been escalated to you as it has remained unresolved:</p>
            <ul>
                <li><strong>Project:</strong> %s</li>
                <li><strong>Issue:</strong> %s</li>
                <li><strong>Owner:</strong> %s</li>
                <li><strong>Date Identified:</strong> %s</li>
            </ul>
            <p>Please log in to Odoo to review and resolve this roadblock.</p>
        """ % (self.project_id.name, self.name, self.owner_id.name, self.date_identified)
        
        mail_server = self.env['ir.mail_server'].search([], limit=1)
        email_from = mail_server.smtp_user if mail_server else 'noreply@ahadu.bank'
        
        self.env['mail.mail'].sudo().create({
            'subject': subject,
            'email_from': email_from,
            'email_to': sponsor_user.partner_id.email,
            'body_html': body_html,
            'auto_delete': True,
        }).send()
        
        self.message_post(body="Critical issue escalated to Sponsor: %s. Email alert sent." % sponsor_user.name)

    @api.model
    def _cron_escalate_critical_issues(self):
        # Find critical issues open for > 48 hours
        limit_date = fields.Date.today() - datetime.timedelta(days=2)
        open_critical_issues = self.search([
            ('severity', '=', 'critical'),
            ('state', '=', 'open'),
            ('escalated', '=', False),
            ('date_identified', '<=', limit_date)
        ])
        for issue in open_critical_issues:
            issue.action_escalate()


class ProjectChangeRequest(models.Model):
    _name = 'project.change_request'
    _description = 'Project Change Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    code = fields.Char(string="CR Code", readonly=True, copy=False, default="/")
    name = fields.Char(string="CR Title/Subject", required=True, tracking=True)
    project_id = fields.Many2one('project.project', string="Project", required=True, tracking=True)
    
    change_type = fields.Selection([
        ('scope', 'Scope Change'),
        ('budget', 'Budget Adjustment'),
        ('timeline', 'Timeline Schedule Change'),
        ('other', 'Other modification')
    ], string="Change Type", required=True, tracking=True)
    
    description = fields.Text(string="Change Description", required=True, tracking=True)
    impact_assessment = fields.Text(string="Impact Assessment", required=True, tracking=True)
    
    proposed_budget_change = fields.Float(string="Proposed Budget Change Amount", tracking=True)
    proposed_timeline_change = fields.Date(string="Proposed New End Date", tracking=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('reviewed', 'Reviewed'),
        ('approved', 'Approved'),
        ('implemented', 'Implemented'),
        ('closed', 'Closed')
    ], string="Status", default='draft', required=True, tracking=True, copy=False)
    
    requested_by_id = fields.Many2one('res.users', string="Requested By", default=lambda self: self.env.user, readonly=True)
    reviewed_by_id = fields.Many2one('res.users', string="Reviewed By", readonly=True)
    approved_by_id = fields.Many2one('res.users', string="Approved By", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code') or vals.get('code') == '/':
                vals['code'] = self.env['ir.sequence'].next_by_code('project.change_request.seq') or '/'
        return super(ProjectChangeRequest, self).create(vals_list)

    def action_submit(self):
        for cr in self:
            if cr.state != 'draft':
                raise UserError("Only draft Change Requests can be submitted.")
            cr.write({'state': 'submitted'})

    def action_review(self):
        for cr in self:
            if cr.state != 'submitted':
                raise UserError("Only submitted Change Requests can be reviewed.")
            cr.write({
                'state': 'reviewed',
                'reviewed_by_id': self.env.user.id
            })
            cr.message_post(body="Change request reviewed.")

    def action_approve(self):
        for cr in self:
            if cr.state != 'reviewed':
                raise UserError("Only reviewed Change Requests can be approved.")
            
            # Maker-Checker verification
            submitter = cr.create_uid
            if self.env.user == submitter and not self.env.user.has_group('ahadu_project_management.group_pmo_admin'):
                raise ValidationError("Maker-Checker Rule: You cannot approve a Change Request you submitted.")
            
            # Restrict to Sponsor or PMO Admin
            is_sponsor = cr.project_id.project_sponsor_id.user_id == self.env.user
            is_pmo = self.env.user.has_group('ahadu_project_management.group_pmo_admin')
            if not (is_sponsor or is_pmo):
                raise ValidationError("Access Denied: Only the Project Sponsor (%s) or a PMO Administrator can approve this Change Request." % cr.project_id.project_sponsor_id.name)

            cr.write({
                'state': 'approved',
                'approved_by_id': self.env.user.id
            })
            cr.message_post(body="Change request approved. Automatically updating baselines...")
            
            # Apply Changes to Project baseline
            cr._apply_changes_to_project()

    def action_implement(self):
        for cr in self:
            if cr.state != 'approved':
                raise UserError("Only approved Change Requests can be implemented.")
            cr.write({'state': 'implemented'})
            cr.message_post(body="Change request implementation complete.")

    def action_close(self):
        for cr in self:
            if cr.state != 'implemented':
                raise UserError("Only implemented Change Requests can be closed.")
            cr.write({'state': 'closed'})
            cr.message_post(body="Change request closed.")

    def _apply_changes_to_project(self):
        self.ensure_one()
        project = self.project_id
        if self.change_type == 'timeline':
            if self.proposed_timeline_change:
                old_date = project.planned_end_date
                project.write({'planned_end_date': self.proposed_timeline_change})
                project.message_post(body="Timeline Baseline Updated via Approved CR %s: %s -> %s" % (self.code, old_date, self.proposed_timeline_change))
        
        elif self.change_type == 'budget':
            if self.proposed_budget_change != 0.0:
                active_budget = project.active_budget_id
                if active_budget:
                    # Let's see if there is an "Other" category or if we can get/create a category for adjustment
                    category_model = self.env['project.budget.category']
                    adj_category = category_model.search([('name', 'ilike', 'Adjustment')], limit=1)
                    if not adj_category:
                        adj_category = category_model.create({
                            'name': 'CR Budget Adjustment',
                            'description': 'System category for change request adjustments'
                        })
                    
                    # Find if budget line exists for this category
                    line = active_budget.line_ids.filtered(lambda l: l.category_id.id == adj_category.id)
                    if line:
                        line.write({'planned_amount': line.planned_amount + self.proposed_budget_change})
                    else:
                        self.env['project.budget.line'].create({
                            'budget_id': active_budget.id,
                            'category_id': adj_category.id,
                            'planned_amount': self.proposed_budget_change
                        })
                    project.message_post(body="Budget Baseline Updated via Approved CR %s: added %+f to active budget." % (self.code, self.proposed_budget_change))
                else:
                    # If no active budget, create a new approved budget
                    category_model = self.env['project.budget.category']
                    adj_category = category_model.search([('name', 'ilike', 'Adjustment')], limit=1)
                    if not adj_category:
                        adj_category = category_model.create({
                            'name': 'CR Budget Adjustment',
                            'description': 'System category for change request adjustments'
                        })
                    new_budget = self.env['project.budget'].create({
                        'name': 'CR Adjustment Budget (%s)' % self.code,
                        'project_id': project.id,
                        'state': 'approved',
                    })
                    self.env['project.budget.line'].create({
                        'budget_id': new_budget.id,
                        'category_id': adj_category.id,
                        'planned_amount': self.proposed_budget_change
                    })
                    project.message_post(body="New Approved Budget created via Approved CR %s with amount %f" % (self.code, self.proposed_budget_change))

class ProjectProject(models.Model):
    _inherit = 'project.project'

    risk_ids = fields.One2many('project.risk', 'project_id', string="Risks")
    issue_ids = fields.One2many('project.issue', 'project_id', string="Issues")
    change_request_ids = fields.One2many('project.change_request', 'project_id', string="Change Requests")

class ProjectMilestone(models.Model):
    _inherit = 'project.milestone'

    @api.model
    def _cron_send_milestone_reminders(self):
        today = fields.Date.today()
        upcoming_limit = today + datetime.timedelta(days=5)
        # Search upcoming milestone records that are not reached
        upcoming_milestones = self.search([
            ('is_reached', '=', False),
            ('deadline', '>=', today),
            ('deadline', '<=', upcoming_limit)
        ])
        
        for milestone in upcoming_milestones:
            milestone._send_milestone_reminder_email()

    def _send_milestone_reminder_email(self):
        self.ensure_one()
        recipients = self.env['res.partner']
        
        if self.project_id.user_id and self.project_id.user_id.partner_id:
            recipients |= self.project_id.user_id.partner_id
        if self.project_id.project_sponsor_id and self.project_id.project_sponsor_id.user_id and self.project_id.project_sponsor_id.user_id.partner_id:
            recipients |= self.project_id.project_sponsor_id.user_id.partner_id
        
        for task in self.task_ids:
            for user in task.user_ids:
                if user.partner_id:
                    recipients |= user.partner_id
                    
        recipients = recipients.filtered(lambda p: p.email)
        if not recipients:
            return
            
        subject = "Upcoming Milestone Reminder: %s [%s]" % (self.name, self.project_id.name)
        body_html = """
            <p>Dear Stakeholder,</p>
            <p>This is a reminder that the following milestone is approaching its deadline:</p>
            <ul>
                <li><strong>Project:</strong> %s</li>
                <li><strong>Milestone:</strong> %s</li>
                <li><strong>Deadline:</strong> %s</li>
                <li><strong>Associated Tasks Count:</strong> %s</li>
            </ul>
            <p>Please ensure all pending activities are completed to reach this milestone on time.</p>
        """ % (self.project_id.name, self.name, self.deadline, len(self.task_ids))
        
        mail_server = self.env['ir.mail_server'].search([], limit=1)
        email_from = mail_server.smtp_user if mail_server else 'noreply@ahadu.bank'
        
        for partner in recipients:
            self.env['mail.mail'].sudo().create({
                'subject': subject,
                'email_from': email_from,
                'email_to': partner.email,
                'body_html': body_html,
                'auto_delete': True,
            }).send()
            
        self.project_id.message_post(body="Milestone reminder email sent for '%s' (Deadline: %s)." % (self.name, self.deadline))


