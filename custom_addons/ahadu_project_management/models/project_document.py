from odoo import models, fields, api

class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    project_id = fields.Many2one('project.project', string="Project Reference", index=True)
    
    document_type = fields.Selection([
        ('charter', 'Project Charter'),
        ('sign_off', 'Sign-Off Document'),
        ('requirements', 'Requirement Document'),
        ('milestone_evidence', 'Milestone Evidence'),
        ('other', 'Other')
    ], string="Document Type", default='other', tracking=True)
    
    version = fields.Char(string="Version", default="1.0", tracking=True)
    is_restricted = fields.Boolean(string="Is Restricted?", default=False, tracking=True,
                                   help="If checked, only Project Manager, Sponsor, or PMO Admins can view/modify this file.")
