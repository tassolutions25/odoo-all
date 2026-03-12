from attrs import fields
from odoo.addons.website_hr_recruitment.controllers.main import WebsiteHrRecruitment
from odoo.http import request

class WebsiteHrRecruitmentInherit(WebsiteHrRecruitment):
    def jobs(self, **kw):
        response = super().jobs(**kw)
        if response.qcontext.get('jobs'):
            jobs = response.qcontext['jobs'].filtered(
                lambda j: not j.mission_end_date or j.mission_end_date >= fields.Date.today()
            )
            response.qcontext['jobs'] = jobs
        return response
