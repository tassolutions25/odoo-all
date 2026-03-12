import logging
from datetime import date
from odoo import models, fields

_logger = logging.getLogger(__name__)

class HrJob(models.Model):
    _inherit = 'hr.job'
    _order = 'published_date desc'

    mission_start_date = fields.Date(string="Application Start Date")
    mission_end_date = fields.Date(string="Application End Date")

    def is_application_open(self):
        """Return True if today's date is within mission start/end range."""
        today = date.today()
        for job in self:
            if job.mission_start_date and today < job.mission_start_date:
                return False
            # Use date_to instead of mission_end_date for future-proofing
            if job.date_to and today > job.date_to:
                return False
        return True

    def _auto_unpublish_expired_jobs(self):
        """Automatically unpublish expired jobs (daily cron)."""
        today = fields.Date.today()
        all_published_jobs = self.search([('website_published', '=', True)])

        expired_jobs = all_published_jobs.filtered(
            lambda j: j.date_to and j.date_to < today
        )
        skipped_jobs = all_published_jobs - expired_jobs

        if expired_jobs:
            expired_jobs.write({'website_published': False})
            _logger.info(
                "✅ Auto-unpublished %s expired job(s): %s",
                len(expired_jobs),
                ", ".join(expired_jobs.mapped('name'))
            )
        else:
            _logger.info("✅ No expired jobs found to unpublish.")

        if skipped_jobs:
            _logger.info(
                "⏭ Skipped %s job(s) not yet expired or no end date: %s",
                len(skipped_jobs),
                ", ".join(skipped_jobs.mapped('name'))
            )

        return True
