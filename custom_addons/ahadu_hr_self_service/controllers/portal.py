from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.web.controllers.home import Home
from odoo.exceptions import ValidationError
import base64
import logging
import re

_logger = logging.getLogger(__name__)


class AhaduLoginRedirect(Home):
    
    def _login_redirect(self, uid, redirect=None):
        user = request.env['res.users'].browse(uid)
        
        # Check if the logged-in user is an internal employee/admin
        if user.has_group('base.group_user'):
            # If the redirect is empty or points to the standard backend root, force it to the frontend '/'
            if not redirect or redirect in['/web', '/odoo', '/web?', '/odoo?']:
                return '/'
                
        return super(AhaduLoginRedirect, self)._login_redirect(uid, redirect)


class AhaduSelfServicePortal(CustomerPortal):

    def _get_country_list(self):
        return request.env["res.country"].search([])

    def _get_ethiopia_id(self):
        eth = request.env["res.country"].search([("name", "=", "Ethiopia")], limit=1)
        return eth.id if eth else False

    def _get_lang_list(self):
        return request.env["res.lang"].search([("active", "=", True)])

    def _get_bank_list(self):
        return request.env["res.bank"].search([])

    def _get_currency_list(self):
        return request.env["res.currency"].search([])

    @http.route(["/my", "/my/home"], type="http", auth="user", website=True)
    def home(self, **kw):
        if request.env.user.has_group(
            "base.group_user"
        ) and not request.env.user.has_group("base.group_portal"):
            return request.redirect("/my/dashboard")
        return super(AhaduSelfServicePortal, self).home(**kw)

    @http.route(["/my/dashboard"], type="http", auth="user", website=True)
    def self_service_dashboard(self, **kw):
        employee = request.env.user.employee_id
        is_onboarded = False
        if employee:
            approved_request_count = request.env["hr.employee.onboarding"].search_count(
                [("employee_id", "=", employee.id), ("state", "=", "approved")]
            )
            if approved_request_count > 0:
                is_onboarded = True

        values = {
            "is_onboarded": is_onboarded,
        }
        return request.render("ahadu_hr_self_service.self_service_dashboard", values)

    @http.route(["/my/onboarding"], type="http", auth="user", website=True)
    def employee_onboarding_form(self, **kw):
        employee = request.env.user.employee_id
        if not employee:
            return request.render("ahadu_hr_self_service.onboarding_no_employee")

        pending_request = request.env["hr.employee.onboarding"].search(
            [("employee_id", "=", employee.id), ("state", "=", "submitted")],
            limit=1,
        )

        values = {
            "employee": employee,
            "page_name": "onboarding",
            "pending_request": pending_request,
            "countries": self._get_country_list(),
            "languages": self._get_lang_list(),
            "banks": self._get_bank_list(),
            "currencies": self._get_currency_list(),
            "default_country_id": self._get_ethiopia_id(),
        }
        return request.render("ahadu_hr_self_service.employee_onboarding_form", values)

    @http.route(["/my/document_request"], type="http", auth="user", website=True)
    def document_request_form(self, **kw):
        employee = request.env.user.employee_id
        if not employee:
            return request.render("ahadu_hr_self_service.onboarding_no_employee")

        pending_request = request.env["hr.document.request"].search(
            [
                ("employee_id", "=", employee.id),
                ("state", "in", ["draft", "submitted"]),
            ],
            limit=1,
        )

        values = {
            "pending_request": pending_request,
            "page_name": "document_request",
        }
        return request.render("ahadu_hr_self_service.document_request_form", values)

    @http.route(
        ["/my/document_request/submit"],
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def document_request_submit(self, **kw):
        employee = request.env.user.employee_id
        if not employee:
            return request.render("ahadu_hr_self_service.onboarding_no_employee")

        try:
            vals = {
                "employee_id": employee.id,
                "document_type": kw.get("document_type"),
                "reason": kw.get("reason"),
            }

            if kw.get("document_file"):
                file_content = kw.get("document_file").read()
                vals["document_file"] = base64.b64encode(file_content)
                vals["document_filename"] = kw.get("document_file").filename

            doc_request = request.env["hr.document.request"].sudo().create(vals)
            doc_request.sudo().action_submit()

            return request.render(
                "ahadu_hr_self_service.document_request_submit_success"
            )

        except (ValidationError, Exception) as e:
            _logger.error(
                "Error during document request submission: %s", e, exc_info=True
            )
            return request.render(
                "website.http_error",
                {
                    "status_code": "Submission Error",
                    "status_message": _("An error occurred: %s", e),
                },
            )

    @http.route(
        ["/my/onboarding/submit"],
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def employee_onboarding_submit(self, **kw):
        employee = request.env.user.employee_id
        if not employee:
            return request.render("ahadu_hr_self_service.onboarding_no_employee")

        try:

            def safe_int(val):
                return int(val) if val and str(val).isdigit() else False

            
            vals = {
                "employee_id": employee.id,
                # Personal Info
                "salutation": kw.get("salutation"),
                "gender_updated": kw.get("gender"),
                "birthday": kw.get("birthday") or None,
                "birth_place": kw.get("birth_place"),
                "nationality_id": safe_int(kw.get("nationality_id")),
                "country_id": safe_int(kw.get("country_id")),
                "subcity": kw.get("subcity"),
                "marital": kw.get("marital"),
                "wedding_date": kw.get("wedding_date") or None,
                "language_ids": [
                    (
                        6,
                        0,
                        [
                            int(lang)
                            for lang in request.httprequest.form.getlist("language_ids")
                        ],
                    )
                ],
                "blood_group": kw.get("blood_group"),
                "physical_challenge": kw.get("physical_challenge"),
                "physical_challenge_detail": kw.get("physical_challenge_detail"),
                "identification_id": kw.get("national_id_number"),
                "kebele_id": kw.get("kebele_id_number"),
                # Contact Detail
                "work_phone": kw.get("work_phone"),
                "mobile_phone": kw.get("private_phone"),
                "work_email": kw.get("work_email"),
                "private_email": kw.get("private_email"),
                "subcity": kw.get("current_address_subcity"),
                "woreda": kw.get("current_address_woreda"),
                "house_number": kw.get("current_address_house_number"),
                "permanent_address_city": kw.get("permanent_address_city"),
                "permanent_address_country_id": safe_int(
                    kw.get("permanent_address_country_id")
                ),
                # Emergency Contact
                "emergency_contact_name": kw.get("emergency_name"),
                "emergency_contact_relationship": kw.get("emergency_relationship"),
                "emergency_contact_address_city": kw.get("emergency_address_city"),
                "emergency_contact_address_country_id": safe_int(
                    kw.get("emergency_address_country_id")
                ),
                "emergency_contact_phone": kw.get("emergency_phone"),
                # Passport
                "passport_name": kw.get("passport_name"),
                "passport_id": kw.get("passport_number"),
                "passport_issue_place": kw.get("passport_issue_place"),
                "passport_issue_date": kw.get("passport_issue_date") or None,
                "passport_expiry_date": kw.get("passport_expiry_date") or None,
                "encr_required": kw.get("encr_required"),
                # Cost-Sharing
                "cost_sharing_institution": kw.get("cost_sharing_institution"),
                "cost_sharing_status": kw.get("cost_sharing_status"),
                "cost_sharing_amount": float(kw.get("cost_sharing_amount") or 0.0),
            }

            # File Uploads
            if kw.get("national_id_file"):
                f = kw.get("national_id_file")
                vals["national_id_file"] = base64.b64encode(f.read())
                vals["national_id_filename"] = f.filename
            if kw.get("kebele_id_file"):
                f = kw.get("kebele_id_file")
                vals["kebele_id_file"] = base64.b64encode(f.read())
                vals["kebele_id_filename"] = f.filename
            if kw.get("passport_file"):
                f = kw.get("passport_file")
                vals["passport_file"] = base64.b64encode(f.read())
                vals["passport_filename"] = f.filename
            if kw.get("cost_sharing_document"):
                f = kw.get("cost_sharing_document")
                vals["cost_sharing_document"] = base64.b64encode(f.read())
                vals["cost_sharing_document_filename"] = f.filename

            # 2. Handle Dynamic Bank Rows
            bank_vals_list = []
            bank_keys = [k for k in kw.keys() if k.startswith("bank_name_")]
            for key in bank_keys:
                idx = key.split("_")[-1]
                if kw.get(f"bank_account_number_{idx}"):
                    bank_vals_list.append(
                        (
                            0,
                            0,
                            {
                                "bank_id": safe_int(kw.get(f"bank_name_{idx}")),
                                "bank_country_id": safe_int(
                                    kw.get(f"bank_country_id_{idx}")
                                ),
                                "account_number": kw.get(f"bank_account_number_{idx}"),
                                "currency_id": safe_int(
                                    kw.get(f"bank_currency_id_{idx}")
                                ),
                                "account_holder_name": kw.get(
                                    f"bank_account_holder_{idx}"
                                ),
                                "account_type": kw.get(f"bank_account_type_{idx}"),
                            },
                        )
                    )
            if bank_vals_list:
                vals["bank_account_ids"] = bank_vals_list

            # 3. Handle Dynamic Family Rows
            family_vals = []
            family_keys = [k for k in kw.keys() if k.startswith("family_relationship_")]
            for key in family_keys:
                idx = key.split("_")[-1]
                if kw.get(f"family_full_name_{idx}"):
                    family_vals.append(
                        (
                            0,
                            0,
                            {
                                "relationship": kw.get(f"family_relationship_{idx}"),
                                "full_name": kw.get(f"family_full_name_{idx}"),
                                "contact_number": kw.get(f"family_contact_{idx}"),
                                "gender": kw.get(f"family_gender_{idx}"),
                                "nationality_id": safe_int(
                                    kw.get(f"family_nationality_{idx}")
                                ),
                                "dependent": kw.get(f"family_dependent_{idx}") == "yes",
                                "insured": kw.get(f"family_insured_{idx}") == "yes",
                            },
                        )
                    )
            if family_vals:
                vals["family_ids"] = family_vals

            # 4. Handle Dynamic Education Rows
            education_vals = []
            edu_keys = [k for k in kw.keys() if k.startswith("edu_institution_type_")]
            for key in edu_keys:
                idx = key.split("_")[-1]
                if kw.get(f"edu_school_{idx}"):
                    edu_cert_file = kw.get(f"edu_certificate_{idx}")
                    keep_file = kw.get(f"edu_keep_file_{idx}")

                    # Basic values
                    line_vals = {
                        "type_of_institution": kw.get(f"edu_institution_type_{idx}"),
                        "school": kw.get(f"edu_school_{idx}"),
                        "certificate_level": kw.get(f"edu_level_{idx}"),
                        "field_of_study": kw.get(f"edu_field_{idx}"),
                        "cgpa": float(kw.get(f"edu_cgpa_{idx}") or 0.0),
                        "start_date": kw.get(f"edu_start_date_{idx}") or None,
                        "end_date": kw.get(f"edu_end_date_{idx}") or None,
                    }

                    # File handling
                    if edu_cert_file:
                        line_vals["certification_attachment"] = base64.b64encode(
                            edu_cert_file.read()
                        )
                        line_vals["certification_filename"] = edu_cert_file.filename
                    elif keep_file:
                        pass

                    education_vals.append((0, 0, line_vals))
            if education_vals:
                vals["education_ids"] = education_vals

            # Create Record
            onboarding_request = (
                request.env["hr.employee.onboarding"].sudo().create(vals)
            )
            onboarding_request.sudo().action_submit()

            return request.render("ahadu_hr_self_service.onboarding_submit_success")

        except (ValidationError, Exception) as e:
            _logger.error("Error during onboarding submission: %s", e, exc_info=True)
            return request.render(
                "ahadu_hr_self_service.submission_error",
                {
                    "error_message": str(e),
                },
            )
