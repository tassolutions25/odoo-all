from odoo import http
from odoo.http import request
from odoo.addons.website_hr_recruitment.controllers import main as hr_main
from datetime import datetime, date

class WebsiteHrRecruitmentOverride(hr_main.WebsiteHrRecruitment):
    @http.route(['/jobs'], type='http', auth="public", website=True)
    def jobs(self, **kwargs):
        # Get default /jobs response and qcontext
        response = super().jobs(**kwargs)
        jobs = response.qcontext.get('jobs')

        if jobs:
            def normalize_date(value):
                """Convert any date or datetime to datetime for safe comparison."""
                if isinstance(value, datetime):
                    return value
                elif isinstance(value, date):
                    # Convert date to datetime (00:00 time)
                    return datetime.combine(value, datetime.min.time())
                else:
                    # fallback for missing date
                    return datetime.min

            # Sort by published_date descending (most recent first)
            response.qcontext['jobs'] = jobs.sorted(
                key=lambda j: normalize_date(j.published_date),
                reverse=True
            )

        return response
