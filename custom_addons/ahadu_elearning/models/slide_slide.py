# -*- coding: utf-8 -*-
from odoo import models, fields, api
from markupsafe import Markup
import re
import mimetypes


class SlideSlide(models.Model):
    _inherit = 'slide.slide'

    video_binary_content = fields.Binary('Video Content', attachment=True)
    video_binary_filename = fields.Char('Video Filename')
    video_attachment_ids = fields.Many2many('ir.attachment', string="Video Attachment")
    source_type = fields.Selection(selection_add=[
        ('external_link', 'External Link')
    ], ondelete={'external_link': 'set default'})

    @api.depends('slide_category', 'source_type', 'video_binary_content', 'video_attachment_ids', 'video_url', 'embed_code')
    def _compute_embed_code(self):
        super(SlideSlide, self)._compute_embed_code()
        for slide in self:
            if slide.slide_category == 'video':
                if slide.source_type == 'local_file':
                    video_url = False
                    mime_type = 'video/mp4'

                    if slide.video_attachment_ids:
                        attachment = slide.video_attachment_ids[0]
                        video_url = f"/web/content/{attachment.id}"
                        # Auto-detect MIME type from the file name
                        if attachment.name:
                            detected_mime, _ = mimetypes.guess_type(attachment.name)
                            if detected_mime:
                                mime_type = detected_mime
                        elif attachment.mimetype:
                            mime_type = attachment.mimetype
                    elif slide.video_binary_content:
                        video_url = f"/web/content/slide.slide/{slide.id}/video_binary_content"
                        if slide.video_binary_filename:
                            detected_mime, _ = mimetypes.guess_type(slide.video_binary_filename)
                            if detected_mime:
                                mime_type = detected_mime

                    if video_url:
                        # Use 'video' type so Odoo's fullscreen JS renders it as an article (html content)
                        # by overriding video_source_type to 'local_file' — we handle display ourselves
                        slide.embed_code = Markup(
                            '<video style="width:100%;height:100%;max-height:100vh;" controls controlsList="nodownload">'
                            '<source src="{url}" type="{mime}">'
                            'Your browser does not support the video tag.'
                            '</video>'
                        ).format(url=video_url, mime=mime_type)
                        slide.embed_code_external = slide.embed_code
                elif slide.source_type == 'external' and slide.video_url:
                    file_id = False
                    if '/file/d/' in slide.video_url:
                        match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', slide.video_url)
                        if match:
                            file_id = match.group(1)
                    elif 'id=' in slide.video_url:
                        match = re.search(r'id=([a-zA-Z0-9_-]+)', slide.video_url)
                        if match:
                            file_id = match.group(1)

                    if file_id:
                        embed_url = f"https://drive.google.com/file/d/{file_id}/preview"
                        slide.embed_code = Markup(
                            '<iframe src="{url}" width="100%" height="500" frameborder="0" allow="autoplay" allowfullscreen></iframe>'
                        ).format(url=embed_url)
                        slide.embed_code_external = slide.embed_code

    def _make_video_attachments_public(self):
        """Make video attachments public so website visitors can view the video."""
        for slide in self:
            if slide.video_attachment_ids:
                slide.video_attachment_ids.sudo().write({'public': True})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._make_video_attachments_public()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'video_attachment_ids' in vals:
            self._make_video_attachments_public()
        return res
