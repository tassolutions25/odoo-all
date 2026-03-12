from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HrEmployeeEducation(models.Model):
    _name = "hr.employee.education"
    _description = "Employee Education History"
    _order = "end_date desc, id desc"

    employee_id = fields.Many2one("hr.employee", string="Employee", ondelete="cascade")

    onboarding_id = fields.Many2one(
        "hr.employee.onboarding", string="Onboarding Request", ondelete="cascade"
    )

    type_of_institution = fields.Selection(
        [
            ("high_school", "High School"),
            ("tvet", "TVET"),
            ("college", "College"),
            ("university", "University"),
        ],
        string="Type of Institution",
        required=True,
    )
    school = fields.Char(string="School / University", required=True)
    certificate_level = fields.Selection(
        [
            ("high_school", "High School"),
            ("diploma", "Diploma"),
            ("bachelor", "Bachelor's Degree"),
            ("master", "Master's Degree"),
            ("phd", "PhD"),
            ("other", "Other"),
        ],
        string="Level of Education",
        required=True,
    )
    field_of_study = fields.Char(string="Field of Study", required=True)
    start_date = fields.Date(string="Start Date", required=True)
    end_date = fields.Date(string="Graduation Date", required=True)
    cgpa = fields.Float(string="CGPA", digits=(3, 2), required=True)
    certification_attachment = fields.Binary(string="Certificate", required=True)
    certification_filename = fields.Char(string="Certificate Filename")

    program = fields.Selection(
        [("regular", "Regular"), ("distance", "Distance"), ("extension", "Extension")],
        string="Educational Program",
    )

    @api.constrains("cgpa")
    def _check_cgpa(self):
        for record in self:
            if record.cgpa < 0 or record.cgpa > 5:
                raise ValidationError(
                    _("CGPA must be a positive value, typically not exceeding 5.0.")
                )

    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        for record in self:
            if (
                record.start_date
                and record.end_date
                and record.start_date > record.end_date
            ):
                raise ValidationError(
                    _("The graduation date cannot be earlier than the start date.")
                )

    @api.constrains("certification_filename")
    def _check_file_extension(self):
        for record in self:
            if (
                record.certification_filename
                and not record.certification_filename.lower().endswith(
                    (".pdf", ".png", ".jpg", ".jpeg")
                )
            ):
                raise ValidationError(
                    _(
                        "Invalid file format for certificate. Please upload a PDF, PNG, or JPG file."
                    )
                )
