from odoo import models, fields, api


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    onboarding_ids = fields.One2many(
        "hr.employee.onboarding", "employee_id", string="Onboarding Requests"
    )
    document_request_ids = fields.One2many(
        "hr.document.request", "employee_id", string="Document Requests"
    )

    onboarding_status = fields.Selection([
        ('not_started', 'Not Started'),
        ('pending', 'Pending (Draft/Submitted/Rejected)'),
        ('completed', 'Completed')
    ], string="Onboarding Status", compute="_compute_onboarding_stats", store=True, index=True)

    personal_completion = fields.Float(string="Personal Info (%)", compute="_compute_onboarding_stats", store=True)
    contact_completion = fields.Float(string="Contact Details (%)", compute="_compute_onboarding_stats", store=True)
    emergency_completion = fields.Float(string="Emergency Contact (%)", compute="_compute_onboarding_stats", store=True)
    bank_completion = fields.Float(string="Bank Details (%)", compute="_compute_onboarding_stats", store=True)
    family_completion = fields.Float(string="Family Details (%)", compute="_compute_onboarding_stats", store=True)
    education_completion = fields.Float(string="Education Details (%)", compute="_compute_onboarding_stats", store=True)
    experience_completion = fields.Float(string="Previous Experience (%)", compute="_compute_onboarding_stats", store=True)
    passport_completion = fields.Float(string="Passport Details (%)", compute="_compute_onboarding_stats", store=True)
    cost_sharing_completion = fields.Float(string="Cost-Sharing (%)", compute="_compute_onboarding_stats", store=True)
    onboarding_completion_rate = fields.Float(string="Overall Onboarding Progress (%)", compute="_compute_onboarding_stats", store=True)

    @api.depends(
        'onboarding_ids.state',
        'onboarding_ids.personal_completion',
        'onboarding_ids.contact_completion',
        'onboarding_ids.emergency_completion',
        'onboarding_ids.bank_completion',
        'onboarding_ids.family_completion',
        'onboarding_ids.education_completion',
        'onboarding_ids.experience_completion',
        'onboarding_ids.passport_completion',
        'onboarding_ids.cost_sharing_completion',
        'onboarding_ids.onboarding_completion_rate'
    )
    def _compute_onboarding_stats(self):
        for employee in self:
            latest_onboarding = self.env['hr.employee.onboarding'].search(
                [('employee_id', '=', employee.id)],
                order='create_date desc',
                limit=1
            )
            if not latest_onboarding:
                employee.onboarding_status = 'not_started'
                employee.personal_completion = 0.0
                employee.contact_completion = 0.0
                employee.emergency_completion = 0.0
                employee.bank_completion = 0.0
                employee.family_completion = 0.0
                employee.education_completion = 0.0
                employee.experience_completion = 0.0
                employee.passport_completion = 0.0
                employee.cost_sharing_completion = 0.0
                employee.onboarding_completion_rate = 0.0
            else:
                if latest_onboarding.state == 'approved':
                    employee.onboarding_status = 'completed'
                else:
                    employee.onboarding_status = 'pending'

                employee.personal_completion = latest_onboarding.personal_completion
                employee.contact_completion = latest_onboarding.contact_completion
                employee.emergency_completion = latest_onboarding.emergency_completion
                employee.bank_completion = latest_onboarding.bank_completion
                employee.family_completion = latest_onboarding.family_completion
                employee.education_completion = latest_onboarding.education_completion
                employee.experience_completion = latest_onboarding.experience_completion
                employee.passport_completion = latest_onboarding.passport_completion
                employee.cost_sharing_completion = latest_onboarding.cost_sharing_completion
                employee.onboarding_completion_rate = latest_onboarding.onboarding_completion_rate

