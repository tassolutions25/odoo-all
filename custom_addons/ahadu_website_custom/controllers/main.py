import base64
import logging
import re
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

NUM_FIELDS = {
    'age': int,
    'years_in_current_position': float,
    'current_salary': float,
    'salary_expectation': float,
    'total_years_banking_exp': float,
    'interview_score': float,
    'written_exam_score': float,
}

# Accept both common website field names and model field names
ALLOWED_FIELDS = {
    'partner_name', 'email_from', 'partner_phone', 'job_id',
    'age', 'gender',
    'educational_qualification', 'institution_name',
    'current_position', 'years_in_current_position', 'current_employer',
    'current_salary', 'salary_expectation',
    'total_years_banking_exp', 'current_location',
    'partner_email',
    'linkedin_profile',
}

NAME_MAP = {
    'email_from': 'email_from',
    'partner_email': 'email_from',
    'partner_name': 'partner_name',
    'partner_phone': 'partner_phone',
    'job_id': 'job_id',
}


class WebsiteHrRecruitmentCustom(http.Controller):

    @http.route(['/ahadu/jobs/apply_custom'], type='http', auth='public', methods=['POST'], website=True)
    def apply_custom(self, **post):
        env = request.env
        _logger.info("=== Received /ahadu/jobs/apply_custom POST ===")

        # Log POST keys for debugging
        for k, v in post.items():
            _logger.info(
                "POST key=%s value_preview=%s",
                k,
                (v[:200] + '...') if isinstance(v, str) and len(v) > 200 else v
            )

        vals = {}

        # Build values from POST
        for k, v in post.items():
            if k not in ALLOWED_FIELDS and k not in NAME_MAP:
                continue
            model_field = NAME_MAP.get(k, k)
            val = (v or "").strip() if isinstance(v, str) else v
            if not val:
                continue

            if model_field in NUM_FIELDS:
                try:
                    vals[model_field] = NUM_FIELDS[model_field](val)
                except Exception:
                    _logger.warning(
                        "Failed to cast numeric field %s value=%r, defaulting to 0",
                        model_field, val
                    )
                    vals[model_field] = 0
            else:
                vals[model_field] = val

        # ---------------------------------------------------------------------
        # ✅ Name validation logic (added)
        # ---------------------------------------------------------------------
        name = vals.get('partner_name', '').strip()
        if not name:
            _logger.warning("Missing name in application submission")
            return request.make_json_response({
                'success': False,
                'error': "Full name is required."
            })

        # Allow only letters, spaces, hyphens, apostrophes
        if not re.match(r"^[A-Za-zÀ-ÿ' -]{2,}$", name):
            _logger.warning("Invalid name submitted: %s", name)
            return request.make_json_response({
                'success': False,
                'error': "Please enter a valid full name (letters only)."
            })

        # Normalize gender
        if 'gender' in vals and vals['gender'] not in ('male', 'female'):
            _logger.warning("Invalid gender value %r removed", vals['gender'])
            vals.pop('gender', None)

        # Convert job_id
        if 'job_id' in vals:
            try:
                vals['job_id'] = int(vals['job_id'])
            except Exception:
                _logger.warning("job_id casting failed for %r", vals['job_id'])
                vals.pop('job_id', None)

        _logger.info("Final vals to create hr.applicant: %s", vals)

        # ---------------------------------------------------------------------
        # Ensure candidate record exists
        # ---------------------------------------------------------------------
        try:
            email = vals.get('email_from')
            candidate = False
            if email:
                candidate = env['hr.candidate'].sudo().search(
                    [('email_from', '=', email)], limit=1
                )
            if not candidate:
                candidate_vals = {}
                if 'partner_name' in vals:
                    candidate_vals['partner_name'] = vals['partner_name']
                if email:
                    candidate_vals['email_from'] = email
                if 'partner_phone' in vals:
                    candidate_vals['partner_phone'] = vals['partner_phone']
                if 'linkedin_profile' in vals:
                    candidate_vals['linkedin_profile'] = vals['linkedin_profile']

                _logger.info("Creating hr.candidate with values: %s", candidate_vals)
                candidate = env['hr.candidate'].sudo().create(candidate_vals)

            vals['candidate_id'] = candidate.id
            _logger.info("Linked or created hr.candidate id=%s for applicant", candidate.id)

            if 'salary_expectation' in vals:
                try:
                    candidate.sudo().write({'salary_expectation': vals['salary_expectation']})
                except Exception as e:
                    _logger.warning("⚠️ Failed to sync salary_expectation: %s", e)

            if 'linkedin_profile' in vals:
                try:
                    candidate.sudo().write({'linkedin_profile': vals['linkedin_profile']})
                except Exception as e:
                    _logger.debug("Skipping linkedin_profile write: %s", e)

        except Exception as e:
            _logger.exception("Failed ensuring candidate record: %s", e)
            return request.redirect('/jobs?error=1')

        # ---------------------------------------------------------------------
        # Normalize & validate Ethiopian phone
        # ---------------------------------------------------------------------
        ETHIOPIAN_PHONE_REGEX = re.compile(r"^\+2519\d{8}$")

        phone = vals.get('partner_phone')
        if phone:
            phone = phone.strip().replace(" ", "")
            if phone.startswith('09'):
                phone = '+251' + phone[1:]
            vals['partner_phone'] = phone

            if not ETHIOPIAN_PHONE_REGEX.match(phone):
                _logger.warning("Invalid Ethiopian phone submitted: %s", phone)
                return request.make_json_response({
                    'success': False,
                    'error': "Invalid Ethiopian phone number. Use +251911123456."
                })

        # ---------------------------------------------------------------------
        # ✅ NEW: Validate uploaded documents before applicant creation
        # ---------------------------------------------------------------------
        try:
            uploaded_files = request.httprequest.files.getlist('application_documents')
            allowed_mimes = ['application/pdf', 'image/png', 'image/jpeg']

            if not uploaded_files:
                _logger.warning("No document uploaded in application submission")
                return request.make_json_response({
                    'success': False,
                    'error': "Please upload at least one document (PDF or image)."
                })

            for f in uploaded_files:
                if f.content_type not in allowed_mimes:
                    _logger.warning("Invalid file type uploaded: %s (%s)", f.filename, f.content_type)
                    return request.make_json_response({
                        'success': False,
                        'error': f"Invalid file type: {f.filename}. Only PDF, PNG, or JPEG allowed."
                    })

            attachments = []
            for f in uploaded_files:
                data = f.read()
                attachments.append((f.filename, base64.b64encode(data).decode()))

        except Exception as e:
            _logger.exception("Error validating uploaded documents: %s", e)
            return request.make_json_response({
                'success': False,
                'error': "There was a problem validating your uploaded files. Please try again."
            })

        # ---------------------------------------------------------------------
        # Create the applicant record
        # ---------------------------------------------------------------------
        try:
            if 'salary_expectation' in vals:
                vals['salary_expected'] = vals['salary_expectation']

            applicant = env['hr.applicant'].sudo().create(vals)
            _logger.info("Created hr.applicant id=%s for candidate=%s", applicant.id, vals['candidate_id'])

            # Attach uploaded files
            for filename, b64data in attachments:
                env['ir.attachment'].sudo().create({
                    'name': filename,
                    'res_model': 'hr.applicant',
                    'res_id': applicant.id,
                    'type': 'binary',
                    'datas': b64data,
                })
            _logger.info("✅ Attached uploaded documents to applicant %s", applicant.id)

            # Send confirmation email
            try:
                template = env.ref('hr_recruitment.email_template_data_applicant_congratulations', raise_if_not_found=False)
                if template:
                    template.sudo().send_mail(applicant.id, force_send=True)
                    _logger.info("✅ Sent confirmation email using hr_recruitment template to: %s", applicant.email_from)
                elif applicant.email_from:
                    mail_vals = {
                        'subject': "Application received",
                        'body_html': "<p>Thank you for applying. We received your application.</p>",
                        'email_to': applicant.email_from,
                        'auto_delete': True,
                        'model': 'hr.applicant',
                        'res_id': applicant.id,
                    }
                    mail = env['mail.mail'].sudo().create(mail_vals)
                    mail.sudo().send()
                    _logger.info("✅ Sent fallback confirmation mail to: %s", applicant.email_from)
            except Exception as e:
                _logger.exception("❌ Failed to send confirmation email: %s", e)

        except Exception as e:
            _logger.exception("Failed to create hr.applicant: %s", e)
            return request.redirect('/jobs?error=1')

        # ---------------------------------------------------------------------
        # ✅ Return JSON response
        # ---------------------------------------------------------------------
        return request.redirect('/jobs/thankyou')

    @http.route(['/jobs/thankyou'], type='http', auth='public', website=True)
    def jobs_thankyou(self, **kw):
        return request.render('ahadu_website_custom.jobs_thankyou_template')
