import logging
from odoo import models, fields, api
from odoo.exceptions import ValidationError


_logger = logging.getLogger(__name__)  # Add this line

class HrApplicant(models.Model):
    _inherit = "hr.applicant"

    employee_id = fields.Char(
        string="Employee ID",
        copy=False
    )

    # New fields for Age and Gender
    age = fields.Integer(
        string="Age", 
        required=True, 
        store=True, 
        default=0
    )
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
    ], 
    string="Gender", 
    required=True, 
    store=True, 
    default='male'
    )

    linkedin_profile = fields.Char(string="LinkedIn Profile", required=False)
 
    # Education
    educational_qualification = fields.Char(
        string="Educational Qualification", 
        required=True, 
        store=True, 
        default="Not Specified"
    )
    institution_name = fields.Char(
        string="Name of Institution", 
        required=True, 
        store=True, 
        default="Not Specified"
    )

    # Current Employment
    current_position = fields.Char(
        string="Current Position", 
        required=True, 
        store=True, 
        default="Not Specified"
    )
    years_in_current_position = fields.Float(
        string="Years in Current Position", 
        required=False, 
        store=True, 
        default=0.0
    )
    current_employer = fields.Char(
        string="Current Employer", 
        required=True, 
        store=True, 
        default="Not Specified"
    )

    company_currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string="Company Currency",
        readonly=True,
        store=True
    )

    current_salary = fields.Monetary(
        string="Current Salary", 
        currency_field='company_currency_id', 
        required=False, 
        store=True, 
        default=0.0
    )
    salary_expectation = fields.Monetary(
        string="Salary Expectation", 
        currency_field='company_currency_id', 
        required=False, 
        store=True, 
        default=0.0
    )

    # --- Synchronize salary fields ---
    @api.onchange('salary_expectation')
    def _onchange_salary_expectation(self):
        """Keep salary_expected in sync when salary_expectation changes."""
        for record in self:
            if record.salary_expectation:
                record.salary_expected = record.salary_expectation

    @api.onchange('salary_expected')
    def _onchange_salary_expected(self):
        """Keep salary_expectation in sync when salary_expected changes."""
        for record in self:
            if record.salary_expected:
                record.salary_expectation = record.salary_expected

    @api.model
    def create(self, vals):
        """Ensure synchronization at record creation."""
        if 'salary_expectation' in vals and not vals.get('salary_expected'):
            vals['salary_expected'] = vals['salary_expectation']
        elif 'salary_expected' in vals and not vals.get('salary_expectation'):
            vals['salary_expectation'] = vals['salary_expected']
        return super(HrApplicant, self).create(vals)

    def write(self, vals):
        """Ensure synchronization on update (write)."""
        for record in self:
            if 'salary_expectation' in vals and 'salary_expected' not in vals:
                vals['salary_expected'] = vals['salary_expectation']
            elif 'salary_expected' in vals and 'salary_expectation' not in vals:
                vals['salary_expectation'] = vals['salary_expected']
        return super(HrApplicant, self).write(vals)

    # Experience
    total_years_banking_exp = fields.Float(
        string="Total Years in Banking Industry", 
        required=True, 
        store=True, 
        default=0.0
    )

    # Location
    current_location = fields.Char(
        string="Current Location", 
        required=True, 
        store=True, 
        default="Not Specified"
    )
    # preferred_location = fields.Char(
    #     string="Preferred Location", 
    #     required=True, 
    #     store=True, 
    #     default="Not Specified"
    # )

    # Documents
    application_documents = fields.Many2many(
        'ir.attachment',
        string="Application Documents",
        help="Upload application letter, updated CV, educational documents, and certificates of service/work experience.",
        store=True
    )

    # --- Interview Evaluation ---
    interview_score = fields.Float(
        string="Interview Score (%)",
        tracking=True,
        help="Enter the weighted score as a percentage (e.g., 85.5)."
    )

    interview_rating = fields.Selection([
        ('0', 'No stars'),
        ('1', 'Normal'),
        ('2', 'Good'),
        ('3', 'Very Good'),
    ],
        string="Interview Rating",
        compute='_compute_interview_rating',
        inverse='_inverse_interview_rating',
        store=True,
        readonly=False,
        tracking=True
    )

    # --- Written Exam ---
    written_exam_score = fields.Float(
        string="Written Exam Score (%)",
        tracking=True,
        help="Enter the written exam score as a percentage (0-100)."
    )

    # --- Combined Score ---
    combined_score = fields.Float(
        string="Average Score (%)",
        compute='_compute_combined_score',
        store=True,
        readonly=True
    )

    # --- Compute/Inverse Logic ---
    @api.depends('interview_score')
    def _compute_interview_rating(self):
        for applicant in self:
            score = applicant.interview_score or 0.0
            if score >= 80:
                applicant.interview_rating = '3'
            elif score >= 60:
                applicant.interview_rating = '2'
            elif score > 0:
                applicant.interview_rating = '1'
            else:
                applicant.interview_rating = '0'

    def _inverse_interview_rating(self):
        for applicant in self:
            rating = applicant.interview_rating
            if rating == '3':
                applicant.interview_score = 80.0
            elif rating == '2':
                applicant.interview_score = 60.0
            elif rating == '1':
                applicant.interview_score = 40.0
            else:
                applicant.interview_score = 0.0

    # --- Compute Combined Score ---
    @api.depends('interview_score', 'written_exam_score')
    def _compute_combined_score(self):
        for applicant in self:
            interview = applicant.interview_score or 0.0
            written = applicant.written_exam_score or 0.0
            applicant.combined_score = (interview + written) / 2.0

    # --- Normalize Ethiopian phone when creating employee ---
    def create_employee_from_applicant(self):
        for applicant in self:
            phone = applicant.partner_phone
            if phone:
                phone = phone.strip().replace(" ", "")
                # Convert 09XXXXXXXX to +2519XXXXXXXX
                if phone.startswith('09'):
                    phone = '+251' + phone[1:]
                # Ensure +251 format stays consistent
                elif not phone.startswith('+251'):
                    _logger.warning(f"⚠️ Unexpected phone format detected: {phone}")
                # Save normalized phone both on applicant and partner
                applicant.partner_phone = phone
                if applicant.partner_id:
                    applicant.partner_id.phone = phone
            else:
                _logger.warning("⚠️ Applicant has no partner_phone to normalize")

        _logger.info("✅ Normalized phone and calling super.create_employee_from_applicant()")
        # Call super without vals (base version takes only self)
        result = super(HrApplicant, self).create_employee_from_applicant()

        # After creation, make sure employee phone is properly normalized
        if result and hasattr(result, 'work_phone'):
            if result.work_phone and not (result.work_phone.startswith('+251') or result.work_phone.startswith('09')):
                result.work_phone = phone
                _logger.info(f"✅ Fixed employee phone after creation: {result.work_phone}")

        return result

    def create_employee_from_applicant(self):
        for applicant in self:
            # Safety check (server-side)
            if applicant.stage_id.name == 'Contract Signed' and not applicant.employee_id:
                raise ValidationError(
                    _("Employee ID is required before creating an employee.")
                )

        # Inject employee_id into context
        self = self.with_context(
            default_employee_id=self.employee_id
        )

        return super().create_employee_from_applicant()
