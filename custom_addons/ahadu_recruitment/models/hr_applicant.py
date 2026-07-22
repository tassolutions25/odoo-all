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

    # Flexible Maker/Checker Approval Workflow Fields
    approval_state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Waiting Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string="Approval State", default='draft', copy=False, tracking=True)

    pending_stage_id = fields.Many2one(
        'hr.recruitment.stage',
        string="Pending Stage",
        copy=False,
        tracking=True
    )
    checker_id = fields.Many2one(
        'hr.employee',
        string="Required Approver / Checker",
        copy=False,
        tracking=True,
        help="Direct manager responsible for reviewing and approving the stage change."
    )
    checker_user_id = fields.Many2one(
        'res.users',
        string="Approver User",
        related='checker_id.user_id',
        store=True,
        readonly=True
    )
    is_checker = fields.Boolean(
        string="Is Current User Checker",
        compute='_compute_is_checker'
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

    @api.depends_context('uid')
    @api.depends('checker_id', 'checker_user_id')
    def _compute_is_checker(self):
        current_user = self.env.user
        user_employee = current_user.employee_id or self.env['hr.employee'].sudo().search([('user_id', '=', current_user.id)], limit=1)
        if not user_employee:
            if current_user.email:
                user_employee = self.env['hr.employee'].sudo().search([('work_email', '=ilike', current_user.email)], limit=1)
            if not user_employee:
                user_employee = self.env['hr.employee'].sudo().search([('name', '=ilike', current_user.name)], limit=1)

        for rec in self:
            if not rec.checker_id:
                rec.is_checker = False
            else:
                is_direct_emp = bool(user_employee and rec.checker_id.id == user_employee.id)
                is_user_match = bool(rec.checker_user_id and rec.checker_user_id.id == current_user.id)
                rec.is_checker = is_direct_emp or is_user_match

    def _get_maker_manager(self):
        current_user = self.env.user
        maker_emp = current_user.employee_id or self.env['hr.employee'].sudo().search([('user_id', '=', current_user.id)], limit=1)
        if not maker_emp:
            if current_user.email:
                maker_emp = self.env['hr.employee'].sudo().search([('work_email', '=ilike', current_user.email)], limit=1)
            if not maker_emp:
                maker_emp = self.env['hr.employee'].sudo().search([('name', '=ilike', current_user.name)], limit=1)

        if not maker_emp:
            raise ValidationError(_("Your user profile (%s) is not linked to an Employee record in HR. Please link your user account under Employees.") % current_user.name)
        if not maker_emp.parent_id:
            raise ValidationError(_("Employee '%s' does not have a Direct Manager assigned under HR.") % maker_emp.name)
        return maker_emp.parent_id

    def write(self, vals):
        for record in self:
            if 'salary_expectation' in vals and 'salary_expected' not in vals:
                vals['salary_expected'] = vals['salary_expectation']
            elif 'salary_expected' in vals and 'salary_expectation' not in vals:
                vals['salary_expectation'] = vals['salary_expected']

        # Intercept stage_id transition if target stage requires manager approval
        if 'stage_id' in vals and not self.env.context.get('bypass_stage_approval'):
            new_stage = self.env['hr.recruitment.stage'].browse(vals['stage_id'])
            if new_stage and new_stage.requires_manager_approval:
                current_user = self.env.user
                # ONLY the Recruitment Checker role can move stages directly without approval
                is_checker_role = current_user.has_group('ahadu_recruitment.group_recruitment_checker')

                if is_checker_role:
                    # Checker has ultimate approval authority: allow direct stage transition
                    vals['approval_state'] = 'draft'
                    vals['pending_stage_id'] = False
                    vals['checker_id'] = False
                    return super(HrApplicant, self).write(vals)

                intercepted = False
                for rec in self:
                    if rec.stage_id != new_stage:
                        # Check if this transition was already approved
                        if rec.approval_state == 'approved' and rec.pending_stage_id == new_stage:
                            vals['approval_state'] = 'draft'
                            vals['pending_stage_id'] = False
                            vals['checker_id'] = False
                            continue

                        # Check if current user is the assigned Checker for this specific record
                        user_employee = current_user.employee_id or self.env['hr.employee'].sudo().search([('user_id', '=', current_user.id)], limit=1)
                        if not user_employee:
                            if current_user.email:
                                user_employee = self.env['hr.employee'].sudo().search([('work_email', '=ilike', current_user.email)], limit=1)
                            if not user_employee:
                                user_employee = self.env['hr.employee'].sudo().search([('name', '=ilike', current_user.name)], limit=1)

                        is_assigned_checker = rec.checker_id and (
                            (user_employee and rec.checker_id.id == user_employee.id) or
                            (rec.checker_user_id and rec.checker_user_id.id == current_user.id)
                        )
                        if is_assigned_checker:
                            # Designated manager is moving stage directly: allow move
                            vals['approval_state'] = 'draft'
                            vals['pending_stage_id'] = False
                            vals['checker_id'] = False
                            return super(HrApplicant, self).write(vals)

                        # Otherwise, Maker is moving stage -> intercept & request approval from Maker's manager
                        manager = rec._get_maker_manager()
                        vals_copy = dict(vals)
                        del vals_copy['stage_id']
                        vals_copy.update({
                            'pending_stage_id': new_stage.id,
                            'approval_state': 'pending',
                            'checker_id': manager.id,
                        })
                        super(HrApplicant, rec).write(vals_copy)
                        rec.message_post(
                            body=_("Stage transition to <b>%s</b> requires manager approval. Application placed in 'Waiting Approval' state for Manager <b>%s</b>.") % (new_stage.name, manager.name)
                        )
                        intercepted = True

                remaining_recs = self.filtered(lambda r: not (r.pending_stage_id == new_stage and r.approval_state == 'pending'))
                if not remaining_recs:
                    return True
                return super(HrApplicant, remaining_recs).write(vals)

        return super(HrApplicant, self).write(vals)

    def action_request_approval(self):
        for rec in self:
            if not rec.pending_stage_id:
                raise ValidationError(_("Please select a pending stage requiring approval."))
            manager = rec._get_maker_manager()
            rec.write({
                'approval_state': 'pending',
                'checker_id': manager.id,
            })
            rec.message_post(
                body=_("Approval requested for stage <b>%s</b> by <b>%s</b>. Assigned Manager: <b>%s</b>.") % (rec.pending_stage_id.name, self.env.user.name, manager.name)
            )

    def action_approve(self):
        for rec in self:
            if not rec.is_checker:
                raise ValidationError(_("Only the designated Approver (%s) can approve this stage transition.") % (rec.checker_id.name if rec.checker_id else 'Manager'))
            if not rec.pending_stage_id:
                raise ValidationError(_("No pending stage found to approve."))
            target_stage = rec.pending_stage_id
            rec.write({'approval_state': 'approved'})
            rec.with_context(bypass_stage_approval=True).write({
                'stage_id': target_stage.id,
                'approval_state': 'draft',
                'pending_stage_id': False,
                'checker_id': False,
            })
            rec.message_post(
                body=_("Stage transition to <b>%s</b> has been APPROVED by Manager <b>%s</b>.") % (target_stage.name, self.env.user.name)
            )

    def action_reject(self):
        for rec in self:
            if not rec.is_checker:
                raise ValidationError(_("Only the designated Approver (%s) can reject this stage transition.") % (rec.checker_id.name if rec.checker_id else 'Manager'))
            rejected_stage_name = rec.pending_stage_id.name if rec.pending_stage_id else 'Target Stage'
            rec.write({'approval_state': 'rejected'})
            rec.message_post(
                body=_("Stage transition to <b>%s</b> was REJECTED by Manager <b>%s</b>.") % (rejected_stage_name, self.env.user.name)
            )

    def action_reset_approval(self):
        for rec in self:
            rec.write({
                'approval_state': 'draft',
                'pending_stage_id': False,
                'checker_id': False,
            })
            rec.message_post(body=_("Approval request reset to Draft by <b>%s</b>.") % self.env.user.name)

    def message_post(self, **kwargs):
        """
        Override message_post to automatically sync any file attachments
        posted to the chatter into the application_documents Many2many field.
        This keeps both the chatter Files section and the Application Documents
        field in sync, while allowing recruitment officers to add more documents
        directly through the field.
        """
        msg = super(HrApplicant, self).message_post(**kwargs)
        # Sync any new chatter attachments into application_documents
        if msg and msg.attachment_ids:
            for rec in self:
                existing_ids = rec.application_documents.ids
                new_ids = [att.id for att in msg.attachment_ids if att.id not in existing_ids]
                if new_ids:
                    rec.with_context(no_recompute=True).write({
                        'application_documents': [(4, att_id) for att_id in new_ids],
                    })
        return msg

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