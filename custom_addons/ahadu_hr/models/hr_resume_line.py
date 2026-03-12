from odoo import models, fields


class ResumeLine(models.Model):
    _inherit = "hr.resume.line"
    _order = "date_end desc, date_start desc, id desc"

    experience_place = fields.Char(string="Institution / Place")
    attachment = fields.Binary(
        string="Attachment",
        attachment=True,
        help="Upload a supporting document for this experience line (e.g., certificate). Allowed formats: PDF, JPG, PNG.",
    )
    attachment_filename = fields.Char(string="Attachment Filename")
