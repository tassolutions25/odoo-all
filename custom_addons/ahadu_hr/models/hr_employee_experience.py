# models/hr_employee_experience.py

from odoo import models, fields, api
from dateutil.relativedelta import relativedelta

class HrEmployeeExperience(models.Model):
    _name = "hr.employee.experience"
    _description = "Employee Previous Experience"
    _order = "end_date desc, start_date desc"

    employee_id = fields.Many2one(
        "hr.employee", 
        string="Employee", 
        required=True, 
        ondelete="cascade"
    )

    company_name = fields.Char(string="Institution / Company", required=True)
    job_title = fields.Char(string="Job Title / Position", required=True)
    location = fields.Char(string="Location / Address")
    
    start_date = fields.Date(string="Start Date", required=True)
    end_date = fields.Date(string="End Date")
    
    previous_salary = fields.Float(string="Previous Salary (CTC)")
    reason_for_leaving = fields.Text(string="Reason for Leaving")
    job_description = fields.Text(string="Job Description / Comments")
    
    # Computed Duration
    duration_years = fields.Float(
        string="Duration (Years)", 
        compute="_compute_experience_duration", 
        store=True,
        help="Experience duration calculated in years."
    )

    attachment = fields.Binary(
        string="Experience Letter/Proof",
        attachment=True,
    )
    attachment_filename = fields.Char(string="Filename")

    @api.depends('start_date', 'end_date')
    def _compute_experience_duration(self):
        for rec in self:
            if rec.start_date:
                end_date = rec.end_date or fields.Date.today()
                if end_date < rec.start_date:
                    rec.duration_years = 0.0
                    continue
                    
                delta = relativedelta(end_date, rec.start_date)
                # Calculate as Years + (Months/12)
                rec.duration_years = round(delta.years + (delta.months / 12.0), 2)
            else:
                rec.duration_years = 0.0