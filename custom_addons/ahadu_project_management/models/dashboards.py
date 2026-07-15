from odoo import models, fields, api, tools

class ProjectDashboardReport(models.Model):
    _name = 'project.dashboard.report'
    _description = 'Project Dashboard Report'
    _auto = False
    _order = 'project_id desc'

    project_id = fields.Many2one('project.project', string="Project", readonly=True)
    project_code = fields.Char(string="Project Code", readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('closed', 'Closed')
    ], string="Workflow State", readonly=True)
    
    planned_start_date = fields.Date(string="Planned Start Date", readonly=True)
    planned_end_date = fields.Date(string="Planned End Date", readonly=True)
    progress = fields.Float(string="Progress (%)", readonly=True)
    
    planned_budget = fields.Float(string="Planned Budget", readonly=True)
    actual_cost = fields.Float(string="Actual Cost", readonly=True)
    budget_variance = fields.Float(string="Variance (Planned - Actual)", readonly=True)
    
    open_risks_count = fields.Integer(string="Open Risks", readonly=True)
    open_issues_count = fields.Integer(string="Open Issues", readonly=True)
    critical_issues_count = fields.Integer(string="Critical Issues", readonly=True)
    change_requests_count = fields.Integer(string="Approved CRs", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    p.id AS id,
                    p.id AS project_id,
                    p.project_code AS project_code,
                    p.state AS state,
                    p.planned_start_date AS planned_start_date,
                    p.planned_end_date AS planned_end_date,
                    p.project_progress AS progress,
                    p.budget_amount AS planned_budget,
                    p.actual_cost AS actual_cost,
                    p.budget_variance AS budget_variance,
                    (SELECT COUNT(*) FROM project_risk r WHERE r.project_id = p.id AND r.state = 'open') AS open_risks_count,
                    (SELECT COUNT(*) FROM project_issue i WHERE i.project_id = p.id AND i.state IN ('draft', 'open')) AS open_issues_count,
                    (SELECT COUNT(*) FROM project_issue i WHERE i.project_id = p.id AND i.state IN ('draft', 'open') AND i.severity = 'critical') AS critical_issues_count,
                    (SELECT COUNT(*) FROM project_change_request cr WHERE cr.project_id = p.id AND cr.state = 'approved') AS change_requests_count
                FROM
                    project_project p
            )
        """ % self._table)
