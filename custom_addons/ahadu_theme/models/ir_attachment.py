from odoo import fields, models

class IrAttachment(models.Model):
    """Inherit 'ir.attachment' to add field"""
    _inherit = 'ir.attachment'

    is_background = fields.Boolean(string="Is Background", default=False,
                                   help="To check is background option added")
