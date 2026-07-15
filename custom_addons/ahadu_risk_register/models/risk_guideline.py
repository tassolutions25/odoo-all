from odoo import models, fields


class RiskGuideline(models.Model):
    _name = 'risk.guideline'
    _description = 'Risk Guideline & Reference Document'
    _order = 'published_date desc, name'

    name = fields.Char(
        string='Title',
        required=True,
        help="Title of the guideline or reference document.",
    )
    description = fields.Text(
        string='Description',
        help="Brief description or summary of the document.",
    )
    document = fields.Binary(
        string='Document',
        attachment=True,
        help="Upload the guideline, policy, or reference document.",
    )
    document_filename = fields.Char(
        string='File Name',
    )
    category = fields.Selection(
        selection=[
            ('guideline', 'Guideline'),
            ('policy', 'Policy'),
            ('manual', 'Manual'),
            ('template', 'Template'),
            ('other', 'Other'),
        ],
        string='Category',
        default='guideline',
        required=True,
    )
    published_date = fields.Date(
        string='Published Date',
    )
    uploaded_by = fields.Many2one(
        'res.users',
        string='Uploaded By',
        default=lambda self: self.env.user,
        readonly=True,
    )
