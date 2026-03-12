from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re


class HrEmployeeOnboarding(models.Model):
    _name = "hr.employee.onboarding"
    _description = "Employee Onboarding Request"
    _inherit = ["hr.approval.mixin", "mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(compute="_compute_name", store=True)
    employee_id = fields.Many2one(
        "hr.employee",
        string="Employee",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    activity_id = fields.Many2one(
        "hr.employee.activity",
        string="Activity Record",
        ondelete="set null",
        readonly=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
        readonly=True,
    )

    # ... Personal Information fields ...
    salutation = fields.Selection(
        [
            ("mr", "Mr."),
            ("mrs", "Mrs."),
            ("ms", "Ms."),
            ("dr", "Dr."),
            ("prof", "Prof."),
        ],
        string="Salutation",
    )
    first_name = fields.Char(related="employee_id.first_name", readonly=True)
    middle_name = fields.Char(related="employee_id.middle_name", readonly=True)
    last_name = fields.Char(related="employee_id.last_name", readonly=True)
    gender_updated = fields.Selection(
        [("male", "Male"), ("female", "Female")], string="Gender"
    )
    birthday = fields.Date(string="Date of Birth")
    birth_place = fields.Char(string="Place of Birth")
    nationality_id = fields.Many2one("res.country", string="Nationality")
    country_id = fields.Many2one("res.country", string="Country of Residence")
    marital = fields.Selection(
        [
            ("single", "Single"),
            ("married", "Married"),
            ("cohabitant", "Legal Cohabitant"),
            ("widower", "Widower"),
            ("divorced", "Divorced"),
        ],
        string="Marital Status",
    )
    wedding_date = fields.Date(string="Wedding Date")
    language_ids = fields.Many2many("res.lang", string="Languages Spoken")
    blood_group = fields.Selection(
        [
            ("A+", "A+"),
            ("A-", "A-"),
            ("B+", "B+"),
            ("B-", "B-"),
            ("O+", "O+"),
            ("O-", "O-"),
            ("AB+", "AB+"),
            ("AB-", "AB-"),
        ],
        string="Blood Group",
    )
    physical_challenge = fields.Selection(
        [("yes", "Yes"), ("no", "No")], string="Physical Challenge"
    )
    physical_challenge_detail = fields.Text(string="Physical Challenge Details")
    identification_id = fields.Char(string="National ID Number")
    national_id_file = fields.Binary(string="National ID File", attachment=True)
    national_id_filename = fields.Char(string="National ID Filename")
    kebele_id = fields.Char(string="Kebele ID Number")
    kebele_id_file = fields.Binary(string="Kebele ID File", attachment=True)
    kebele_id_filename = fields.Char(string="Kebele ID Filename")
    work_phone = fields.Char(string="Work Phone")
    mobile_phone = fields.Char(string="Private Phone")
    work_email = fields.Char(string="Work Email")
    private_email = fields.Char(string="Private Email")
    subcity = fields.Char(string="Current Address: Subcity")
    woreda = fields.Char(string="Current Address: Woreda")
    house_number = fields.Char(string="Current Address: House Number")
    permanent_address_city = fields.Char(string="Permanent Address City")
    permanent_address_country_id = fields.Many2one(
        "res.country", string="Permanent Address Country"
    )
    emergency_contact_name = fields.Char(string="Emergency Contact Name")
    emergency_contact_relationship = fields.Selection(
        [
            ("mother", "Mother"),
            ("father", "Father"),
            ("sister", "Sister"),
            ("brother", "Brother"),
            ("spouse", "Spouse"),
            ("aunt", "Aunt"),
            ("uncle", "Uncle"),
            ("son", "Son"),
            ("daughter", "Daughter"),
            ("other", "Other"),
        ],
        string="Emergency Contact Relationship",
    )
    emergency_contact_address_city = fields.Char(string="Emergency Contact City")
    emergency_contact_address_country_id = fields.Many2one(
        "res.country", string="Emergency Contact Country"
    )
    emergency_contact_phone = fields.Char(string="Emergency Contact Phone")

    # ... Relation fields ...
    bank_account_ids = fields.One2many(
        "hr.employee.onboarding.bank.account", "onboarding_id", string="Bank Accounts"
    )
    family_ids = fields.One2many(
        "hr.employee.onboarding.family", "onboarding_id", string="Family Members"
    )
    education_ids = fields.One2many(
        "hr.employee.education", "onboarding_id", string="Education History"
    )

    # Passport Detail
    passport_name = fields.Char(string="Name as on Passport")
    passport_id = fields.Char(string="Passport Number")
    passport_issue_place = fields.Char(string="Place Passport Issued")
    passport_issue_date = fields.Date(string="Passport Issued Date")
    passport_expiry_date = fields.Date(string="Passport Renewal/Expiry Date")
    encr_required = fields.Selection(
        [("yes", "Yes"), ("no", "No")], string="ENCR Required"
    )
    passport_file = fields.Binary(string="Passport File", attachment=True)
    passport_filename = fields.Char(string="Passport Filename")

    # Cost-Sharing
    cost_sharing_institution = fields.Selection(
        [("government", "Government"), ("private", "Private")],
        string="Cost-Sharing Institution",
    )
    cost_sharing_status = fields.Selection(
        [("paid", "Paid"), ("unpaid", "Unpaid"), ("na", "N/A")],
        string="Cost-Sharing Status",
    )

    cost_sharing_amount = fields.Monetary(
        string="Cost-Sharing Commitment Amount", currency_field="currency_id"
    )

    cost_sharing_document = fields.Binary(
        string="Cost-Sharing Document", attachment=True
    )
    cost_sharing_document_filename = fields.Char(
        string="Cost-Sharing Document Filename"
    )


    @api.constrains("mobile_phone", "work_phone", "emergency_contact_phone")
    def _check_ethiopian_phone(self):
        pattern = r"^(\+251|0)(9|7)\d{8}$"
        for rec in self:
            phones_to_check = {
                "Private Phone": rec.mobile_phone,
                "Work Phone": rec.work_phone,
                "Emergency Contact Phone": rec.emergency_contact_phone,
            }
            for label, number in phones_to_check.items():
                if number:
                    clean_number = number.replace(" ", "")
                    if not re.match(pattern, clean_number):
                        raise ValidationError(_("Invalid format for %s.") % label)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.employee_id:
                # Set currency from employee if not set
                if not rec.currency_id:
                    rec.currency_id = rec.employee_id.company_id.currency_id

                activity = self.env["hr.employee.activity"].create(
                    {
                        "employee_id": rec.employee_id.id,
                        "activity_type": "onboarding",
                        "date": fields.Date.today(),
                        "onboarding_id": rec.id,
                        "description": f"Profile update request by {rec.employee_id.name}",
                        "state": "draft",
                    }
                )
                rec.activity_id = activity.id
        return records

    def write(self, vals):
        res = super(HrEmployeeOnboarding, self).write(vals)
        if "state" in vals:
            for rec in self:
                if rec.activity_id:
                    if vals["state"] == "submitted":
                        rec.activity_id.action_submit()
                    elif vals["state"] == "approved":
                        rec.activity_id.action_approve()
                    elif vals["state"] == "rejected":
                        rec.activity_id.action_reject()
                    elif vals["state"] == "draft":
                        rec.activity_id.action_reset_to_draft()
        return res

    @api.depends("employee_id")
    def _compute_name(self):
        for rec in self:
            rec.name = (
                f"Onboarding Data for {rec.employee_id.name}"
                if rec.employee_id
                else "New Onboarding Request"
            )

    def _get_employee_for_approval(self):
        return self.employee_id

    def _perform_final_approval(self):
        self.ensure_one()
        vals_to_write = {}
        simple_fields = [
            "salutation",
            "gender_updated",
            "birthday",
            "birth_place",
            "nationality_id",
            "country_id",
            "marital",
            "wedding_date",
            "blood_group",
            "physical_challenge",
            "physical_challenge_detail",
            "identification_id",
            "national_id_file",
            "national_id_filename",
            "kebele_id",
            "kebele_id_file",
            "kebele_id_filename",
            "work_phone",
            "mobile_phone",
            "work_email",
            "private_email",
            "subcity",
            "woreda",
            "house_number",
            "permanent_address_city",
            "permanent_address_country_id",
            "emergency_contact_name",
            "emergency_contact_relationship",
            "emergency_contact_address_city",
            "emergency_contact_address_country_id",
            "emergency_contact_phone",
            "passport_name",
            "passport_id",
            "passport_issue_place",
            "passport_issue_date",
            "passport_expiry_date",
            "encr_required",
            "passport_file",
            "passport_filename",
            "cost_sharing_institution",
            "cost_sharing_status",
            "cost_sharing_document",
            "cost_sharing_document_filename",
            "cost_sharing_amount",
        ]

        for field_name in simple_fields:
            if self[field_name] or isinstance(self[field_name], (bool, int, float)):
                vals_to_write[field_name] = self[field_name]

        # --- 1. SYNC BANK ACCOUNTS ---
        self.employee_id.bank_account_ids.unlink()
        bank_vals = []
        for line in self.bank_account_ids:
            bank_vals.append(
                (
                    0,
                    0,
                    {
                        "bank_id": line.bank_id.id,
                        "bank_country_id": line.bank_country_id.id,
                        "account_number": line.account_number,
                        "currency_id": line.currency_id.id,
                        "account_type": line.account_type,
                        "account_holder_name": line.account_holder_name
                        or self.employee_id.name,
                    },
                )
            )
        if bank_vals:
            vals_to_write["bank_account_ids"] = bank_vals

        # --- 2. SYNC FAMILY ---
        self.employee_id.family_ids.unlink()
        family_vals = []
        for line in self.family_ids:
            family_vals.append(
                (
                    0,
                    0,
                    {
                        "relationship": line.relationship,
                        "full_name": line.full_name,
                        "contact_number": line.contact_number,
                        "gender": line.gender,
                        "nationality_id": line.nationality_id.id,
                        "dependent": line.dependent,
                        "insured": line.insured,
                    },
                )
            )
        if family_vals:
            vals_to_write["family_ids"] = family_vals

        # --- 3. SYNC EDUCATION ---
        self.employee_id.education_ids.unlink()
        education_vals = []
        for line in self.education_ids:
            education_vals.append(
                (
                    0,
                    0,
                    {
                        "type_of_institution": line.type_of_institution,
                        "school": line.school,
                        "certificate_level": line.certificate_level,
                        "field_of_study": line.field_of_study,
                        "cgpa": line.cgpa,
                        "start_date": line.start_date,
                        "end_date": line.end_date,
                        "certification_attachment": line.certification_attachment,
                        "certification_filename": line.certification_filename,
                        "program": line.program,
                    },
                )
            )
        if education_vals:
            vals_to_write["education_ids"] = education_vals

        # Handle Many2many languages
        if self.language_ids:
            vals_to_write["language_ids"] = [(6, 0, self.language_ids.ids)]

        # Handle Binary clearing
        for bin_field in [
            "national_id_file",
            "kebele_id_file",
            "passport_file",
            "cost_sharing_document",
        ]:
            if not self[bin_field]:
                if bin_field in vals_to_write:
                    del vals_to_write[bin_field]
                if bin_field + "_filename" in vals_to_write:
                    del vals_to_write[bin_field + "_filename"]

        if vals_to_write:
            self.employee_id.write(vals_to_write)

        self.employee_id.message_post(
            body=_("Employee profile updated via Self-Service.")
        )
        if self.activity_id:
            self.activity_id.action_approve()
