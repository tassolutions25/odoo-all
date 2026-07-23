from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError

class ProjectClosureWizard(models.TransientModel):
    _name = 'project.closure.wizard'
    _description = 'Project Closure Wizard'

    project_id = fields.Many2one('project.project', string="Project Reference", required=True)
    closure_reason = fields.Selection([
        ('completed', 'Successful Completion'),
        ('cancelled', 'Cancelled/Terminated'),
        ('suspended', 'Suspended')
    ], string="Closure Reason", required=True, default='completed')
    
    final_cost = fields.Float(string="Final Actual Cost")
    lessons_learned = fields.Text(string="Lessons Learned", required=True)

    @api.model
    def default_get(self, fields_list):
        res = super(ProjectClosureWizard, self).default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id:
            project = self.env['project.project'].browse(active_id)
            res.update({
                'project_id': project.id,
                'final_cost': project.actual_cost,
            })
        return res

    def action_close_project(self):
        self.ensure_one()
        project = self.project_id
        
        # 1. Access right checks: PMO Admin or Project Manager of this project
        if not (self.env.user.has_group('ahadu_project_management.group_pmo_admin') or self.env.user == project.user_id):
            raise UserError("Access Denied: Only the assigned Project Manager or a PMO Admin can initiate project closure.")

        # 2. Check for open critical or high severity issues
        open_issues = self.env['project.issue'].search([
            ('project_id', '=', project.id),
            ('state', 'in', ['draft', 'open']),
            ('severity', 'in', ['high', 'critical'])
        ])
        if open_issues:
            issue_names = ", ".join(open_issues.mapped('name'))
            raise ValidationError("Project Closure Blocked: Cannot close project because there are unresolved High/Critical issues: [%s]. Resolve them first." % issue_names)

        # 3. Check for active/incomplete tasks
        open_tasks = self.env['project.task'].search([
            ('project_id', '=', project.id),
            ('task_status', 'not in', ['completed', 'cancelled'])
        ])
        if open_tasks:
            task_names = ", ".join(open_tasks.mapped('name'))
            raise ValidationError("Project Closure Blocked: Cannot close project because some tasks are still in progress or not started: [%s]. Complete or cancel them first." % task_names)

        # 4. Perform closure and archive
        project.write({
            'state': 'closed',
            'active': False  # Archive the project
        })

        # 5. Post lessons learned and closure details to project chatter for audit trail
        reason_label = dict(self._fields['closure_reason'].selection).get(self.closure_reason, self.closure_reason)
        chatter_body = """
            <div style="font-family: Arial, sans-serif; font-size: 13px;">
                <h4 style="color: #2e7d32; margin-top: 0;">✔ Project Formally Closed & Archived</h4>
                <p><strong>Closure Reason:</strong> %s</p>
                <p><strong>Final Recorded Cost:</strong> %s</p>
                <p><strong>Lessons Learned:</strong></p>
                <blockquote style="border-left: 3px solid #ccc; padding-left: 10px; font-style: italic; color: #555;">
                    %s
                </blockquote>
                <p style="color: #888; font-size: 11px;">Closed by %s on %s</p>
            </div>
        """ % (
            reason_label, 
            self.final_cost, 
            self.lessons_learned.replace('\n', '<br/>'), 
            self.env.user.name, 
            fields.Date.today()
        )
        project.message_post(
            body=chatter_body,
            subtype_xmlid='mail.mt_note',
            message_type='comment'
        )
        return {'type': 'ir.actions.act_window_close'}


class ProjectProject(models.Model):
    _inherit = 'project.project'

    def action_close(self):
        self.ensure_one()
        if self.state != 'active':
            raise UserError("Only active projects can be closed.")
        # Return action to open the Project Closure Wizard
        return {
            'name': 'Project Closure Checklist & Review',
            'type': 'ir.actions.act_window',
            'res_model': 'project.closure.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_project_id': self.id,
                'default_final_cost': self.actual_cost,
            }
        }
