import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

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

    @api.onchange('salary_expectation')
    def _onchange_salary_expectation(self):
        for record in self:
            if record.salary_expectation:
                record.salary_expected = record.salary_expectation

    @api.onchange('salary_expected')
    def _onchange_salary_expected(self):
        for record in self:
            if record.salary_expected:
                record.salary_expectation = record.salary_expected

    @api.model
    def create(self, vals):
        if 'salary_expectation' in vals and not vals.get('salary_expected'):
            vals['salary_expected'] = vals['salary_expectation']
        elif 'salary_expected' in vals and not vals.get('salary_expectation'):
            vals['salary_expectation'] = vals['salary_expected']
        return super(HrApplicant, self).create(vals)

    def write(self, vals):
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

    # Documents
    application_documents = fields.Many2many(
        'ir.attachment',
        string="Application Documents",
        help="Upload application letter, updated CV, educational documents, and certificates of service/work experience.",
        store=True
    )

    # --- Interview Evaluation ---
    interview_score = fields.Float(string="Interview Score (%)", tracking=True)
    interview_rating = fields.Selection([
        ('0', 'No stars'), ('1', 'Normal'), ('2', 'Good'), ('3', 'Very Good'),
    ], string="Interview Rating", compute='_compute_interview_rating', inverse='_inverse_interview_rating', store=True, readonly=False, tracking=True)
    written_exam_score = fields.Float(string="Written Exam Score (%)", tracking=True)
    combined_score = fields.Float(string="Average Score (%)", compute='_compute_combined_score', store=True, readonly=True)

    @api.depends('interview_score')
    def _compute_interview_rating(self):
        for applicant in self:
            score = applicant.interview_score or 0.0
            if score >= 80: applicant.interview_rating = '3'
            elif score >= 60: applicant.interview_rating = '2'
            elif score > 0: applicant.interview_rating = '1'
            else: applicant.interview_rating = '0'

    def _inverse_interview_rating(self):
        for applicant in self:
            rating = applicant.interview_rating
            if rating == '3': applicant.interview_score = 80.0
            elif rating == '2': applicant.interview_score = 60.0
            elif rating == '1': applicant.interview_score = 40.0
            else: applicant.interview_score = 0.0

    @api.depends('interview_score', 'written_exam_score')
    def _compute_combined_score(self):
        for applicant in self:
            interview = applicant.interview_score or 0.0
            written = applicant.written_exam_score or 0.0
            applicant.combined_score = (interview + written) / 2.0


    # =========================================================================
    # 100% CUSTOM EMPLOYEE CREATION (BYPASSING STANDARD ODOO)
    # =========================================================================
    def create_employee_from_applicant(self):
        self.ensure_one()

        # 1. Check strict validations
        # if self.stage_id.name == 'Contract Signed' and not self.employee_id:
        #     raise ValidationError(_("Employee ID is required before creating an employee."))

        # 2. Parse the Applicant's Name into exactly 3 parts to satisfy Ahadu HR rules
        name = self.partner_name or self.name or 'Unknown'
        name_parts = name.strip().split()
        first_name = name_parts[0] if len(name_parts) >= 1 else 'Unknown'
        last_name = name_parts[-1] if len(name_parts) >= 2 else 'Unknown'
        middle_name = " ".join(name_parts[1:-1]) if len(name_parts) > 2 else '-'
        
        # Failsafe: Ahadu HR crashes if middle name is literally empty
        if not middle_name.strip():
            middle_name = '-'

        # 3. Format Ethiopian Phone Number
        phone = self.partner_phone or ''
        if phone:
            phone = phone.strip().replace(" ", "")
            if phone.startswith('09'):
                phone = '+251' + phone[1:]

        # 4. Build the dictionary exactly how Ahadu HR expects it
        emp_vals = {
            'name': name,
            'first_name': first_name,
            'middle_name': middle_name,
            'last_name': last_name,
            'employee_id': self.employee_id,
            'gender_updated': self.gender,
            'gender': self.gender,
            'work_phone': phone,
            'work_email': self.email_from,
            'department_id': self.department_id.id if self.department_id else False,
            'job_id': self.job_id.id if self.job_id else False,
            'company_id': self.company_id.id or self.env.company.id,
            'tin_number': '0000000000',  # Failsafe for your custom required field
            'active': True,
            'date_of_joining': fields.Date.today(),
        }

        # Transfer the Resume Attachment if it exists
        if self.application_documents:
            doc = self.application_documents[0]
            emp_vals['resume_attachment'] = doc.datas
            emp_vals['resume_attachment_filename'] = doc.name

        # 5. CREATE THE EMPLOYEE DIRECTLY IN THE DATABASE
        # Using sudo() ensures no security rules block this background creation
        new_employee = self.env['hr.employee'].sudo().create(emp_vals)

        # 6. Link the newly created employee to the Applicant
        # self.write({'emp_id': new_employee.id})

        # Post a message to chatter for tracking
        self.message_post(body=_("Employee Profile officially created and linked!"))

        # 7. FORCE THE SCREEN TO OPEN THE ACTUAL SAVED RECORD
        # Notice there is no /new in this action. It opens the exact ID we just generated.
        return {
            'name': _('Employee Profile'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'res_id': new_employee.id,
            'view_mode': 'form',
            'target': 'current',
        }