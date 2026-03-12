# ahadu_recruitment/models/recruitment_inherit.py
from odoo import models, fields, api

class AhaduHrJob(models.Model):
    _inherit = 'hr.job'
    _description = 'Ahadu Job Position'

    # grade_id = fields.Many2one('ahadu.job.grade', string='Job Grade')
    cost_center_id = fields.Many2one('account.analytic.account', string='Cost Center')
    time_to_hire = fields.Float(
        string='Time to Hire (Days)',
        compute='_compute_time_to_hire',
        store=True,
        help="Calculates the average number of days between the job's start date and the date candidates reached the Hired stage."
    )
    cost_per_hire = fields.Monetary(string='Cost Per Hire', currency_field='currency_id')
    job_description = fields.Binary(string="Job Description File", attachment=True)
    job_description_filename = fields.Char(string="Filename")
    years_of_experience = fields.Integer(string='Years of Experience')
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )

    # --- Compute Average Time to Hire ---
    @api.depends('application_ids.stage_id', 'date_from')
    def _compute_time_to_hire(self):
        """
        Calculate the average number of days between the job's date_from
        (mission start date) and the date applicants reached the Hired stage.
        """
        for job in self:
            start_date = job.date_from or job.create_date
            hired_applicants = job.application_ids.filtered(
                lambda a: a.stage_id and getattr(a.stage_id, 'hired_stage', False)
            )

            if start_date and hired_applicants:
                total_days = 0
                count = 0
                for applicant in hired_applicants:
                    # Use write_date (last update time) as an approximation of hire date
                    end_date = applicant.write_date.date() if applicant.write_date else None
                    if end_date:
                        diff_days = (fields.Date.from_string(str(end_date)) -
                                     fields.Date.from_string(str(start_date))).days
                        if diff_days >= 0:
                            total_days += diff_days
                            count += 1
                job.time_to_hire = round(total_days / count, 2) if count else 0
            else:
                job.time_to_hire = 0
