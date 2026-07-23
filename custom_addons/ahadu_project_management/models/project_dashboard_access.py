# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ProjectDashboardAccess(models.Model):
    _name = 'project.dashboard.access'
    _description = 'Project Dashboard & Report Access'
    _rec_name = 'dashboard_type'
    _order = 'dashboard_type'

    DASHBOARD_TYPE_SELECTION = [
        ('executive', 'Executive Management Dashboard (CEO/CIO)'),
        ('sponsor', 'Project Sponsor Dashboard'),
        ('pmo', 'IT Program Management & Innovation Directorate Dashboard (PMO)'),
        ('division', 'Enterprise Program & Architecture Division Dashboard'),
        ('pm', 'Project Manager Dashboard'),
        ('team', 'Project Team Member Dashboard'),
    ]

    dashboard_type = fields.Selection(
        DASHBOARD_TYPE_SELECTION, 
        string="Dashboard/Report Role", 
        required=True
    )
    job_ids = fields.Many2many(
        'hr.job', 
        'project_dashboard_access_job_rel',
        'access_id', 
        'job_id', 
        string="Allowed Job Positions",
        help="Job positions allowed to view and export reports for this dashboard role."
    )
    note = fields.Char(string="Note", help="Internal notes or descriptions.")

    _sql_constraints = [
        ('unique_dashboard_type', 'UNIQUE(dashboard_type)', 'An access rule for this dashboard/report role already exists.')
    ]

    @api.model
    def get_authorized_dashboard_roles(self, user=None):
        """
        Returns a list of authorized dashboard types for a given user.
        Based on their linked employee's job position.
        Falls back to group/system defaults if no job mapping matches or no employee profile exists.
        """
        if not user:
            user = self.env.user

        # Fetch linked employee
        employee = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        
        # If no employee profile exists, default to all/admin access fallback
        if not employee:
            return [t[0] for t in self.DASHBOARD_TYPE_SELECTION]

        job_id = employee.job_id.id
        if not job_id:
            # Fallback to group membership
            roles = []
            if user.has_group('ahadu_project_management.group_pmo_admin'):
                roles.append('pmo')
            if user.has_group('ahadu_project_management.group_project_manager'):
                roles.append('pm')
            if user.has_group('ahadu_project_management.group_project_team'):
                roles.append('team')
            return roles if roles else ['team']

        # Find dashboard roles containing the employee's job position
        rules = self.sudo().search([('job_ids', 'in', [job_id])])
        roles = rules.mapped('dashboard_type')

        # Fallback security group mappings if no explicit job mappings exist for any role
        if not roles:
            if user.has_group('ahadu_project_management.group_pmo_admin'):
                roles.append('pmo')
            if user.has_group('ahadu_project_management.group_project_manager'):
                roles.append('pm')
            if user.has_group('ahadu_project_management.group_project_team'):
                roles.append('team')
        
        return list(set(roles)) if roles else ['team']
