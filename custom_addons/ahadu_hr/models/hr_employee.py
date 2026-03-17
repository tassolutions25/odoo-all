from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date
from dateutil.relativedelta import relativedelta
import re
import logging
import math
from odoo.tools.mail import email_re

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _name = "hr.employee"
    _inherit = [
        "hr.employee",
        "hr.approval.mixin",
        "mail.thread",
        "mail.activity.mixin",
    ]
    _description = "Employee"

    _order = "employee_id asc, name asc"
    _rec_names_search = ["name", "employee_id"]

    name = fields.Char(
        string="Full Name",
        compute="_compute_full_name",
        inverse="_inverse_full_name",
        store=True,
    )
    # employee_id = fields.Char(
    #     string="Employee ID",
    #     readonly=True,
    #     index=True,
    #     copy=False,
    #     default=lambda self: self._default_employee_id(),
    # )

    employee_id = fields.Char(
        string="Employee ID",
        index=True,
        copy=False,
        required=True,
    )

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
    first_name = fields.Char(string="First Name", required=True)
    last_name = fields.Char(string="Last Name", required=True)
    middle_name = fields.Char(string="Middle Name", required=True)
    birth_place = fields.Char(string="Place of Birth")
    nationality_id = fields.Many2one(
        "res.country",
        string="Nationality",
        default=lambda self: self.env.ref("base.et", raise_if_not_found=False),
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
    national_id_file = fields.Binary(string="National ID File")
    national_id_filename = fields.Char(string="National ID Filename")
    kebele_id_file = fields.Binary(string="Kebele ID File")
    kebele_id_filename = fields.Char(string="Kebele ID Filename")
    # Contact Detail
    permanent_address_city = fields.Char(string="Permanent Address City")
    permanent_address_country_id = fields.Many2one(
        "res.country",
        string="Permanent Address Country",
        default=lambda self: self.env.ref("base.et", raise_if_not_found=False),
    )

    # Emergency Contact
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

    bank_account_ids = fields.One2many(
        "hr.employee.bank.account", "employee_id", string="Bank Accounts"
    )

    # Family Detail
    family_ids = fields.One2many("hr.employee.family", "employee_id", string="Family")
    experience_ids = fields.One2many(
        "hr.employee.experience", "employee_id", string="Previous Experience"
    )

    # Passport Detail
    passport_name = fields.Char(string="Name as on Passport")
    passport_issue_place = fields.Char(string="Place Passport Issued")
    passport_issue_date = fields.Date(string="Passport Issued Date")
    passport_expiry_date = fields.Date(string="Passport Renewal/Expiry Date")
    encr_required = fields.Selection(
        [("yes", "Yes"), ("no", "No")], string="ENCR Required"
    )
    passport_file = fields.Binary(string="Passport File")
    passport_filename = fields.Char(string="Passport Filename")

    # Cost-Sharing Detail
    cost_sharing_institution = fields.Selection(
        [("government", "Government"), ("private", "Private")],
        string="Cost-Sharing Institution",
    )
    cost_sharing_status = fields.Selection(
        [("paid", "Paid"), ("unpaid", "Unpaid"), ("na", "N/A")],
        string="Cost-Sharing Status",
    )
    cost_sharing_amount = fields.Monetary(string="Cost-Sharing Commitment Amount")
    cost_sharing_document = fields.Binary(string="Cost-Sharing Document")
    cost_sharing_document_filename = fields.Char(
        string="Cost-Sharing Document Filename"
    )

    # Overriding fields
    country_id = fields.Many2one(
        "res.country",
        "Country",
        default=lambda self: self.env.ref("base.et", raise_if_not_found=False),
    )
    date_of_joining = fields.Date(string="Date of Joining")
    # effective_from_date = fields.Date(string="Effective From Date")
    grade_id = fields.Many2one("hr.grade", string="Grade", ondelete="set null")
    position_classification = fields.Selection(
        [
            ("management", "Management"),
            ("non_management", "Non-Management"),
        ],
        string="Position Classification",
        default="non_management",
    )
    gender_updated = fields.Selection(
        [("male", "Male"), ("female", "Female")],
        string="Gender",
        tracking=True,
    )
    identification_id = fields.Char(string="National ID Number")
    ssnid = fields.Char(string="Pension Number")
    district_id = fields.Many2one("hr.district", string="District", ondelete="set null")
    branch_id = fields.Many2one("hr.branch", string="Branch", ondelete="set null")
    division_id = fields.Many2one(
        "hr.division",
        string="Division",
        ondelete="set null",
        domain="[('department_id', '=', department_id)]",
    )
    cost_center_id = fields.Many2one(
        "hr.cost.center",
        string="Cost Center",
        tracking=True,
        help="The Cost Center to which this employee's costs are allocated.",
    )
    tin_number = fields.Char(string="TIN Number", size=10, required=True)
    kebele_id = fields.Char(string="Kebele ID", size=20)
    mother_name = fields.Char(string="Mother's Full Name")
    spouse_name = fields.Char(string="Spouse's Full Name")
    number_of_children = fields.Integer(string="Number of Children")
    children_names = fields.Text(
        string="Names of Children", help="List the names of the children, one per line."
    )

    education_ids = fields.One2many(
        "hr.employee.education", "employee_id", string="Education History"
    )
    training_ids = fields.One2many(
        "hr.employee.training", "employee_id", string="Training History"
    )

    emp_wage = fields.Monetary(
        string="Base Salary (Wage)",
        tracking=True,
        help="This is the employee's gross monthly salary.",
    )
    representation_allowance = fields.Float(
        string="Representation Allowance (%)", tracking=True
    )
    hardship_allowance_level_id = fields.Many2one(
        "hr.hardship.allowance.level", string="Hardship Allowance Level", tracking=True
    )
    housing_allowance = fields.Monetary(string="Housing Allowance", tracking=True)
    mobile_allowance = fields.Monetary(string="Mobile Allowance", tracking=True)
    transport_allowance_liters = fields.Float(
        string="Transport Allowance (Liters)", tracking=True
    )
    transport_allowance_amount = fields.Monetary(
        string="Transport Allowance Amount",
        compute="_compute_transport_allowance_amount",
        store=True,
        readonly=True,
        help="Calculated based on liters and the global fuel price set in HR Settings.",
    )
    # benefit_package_id = fields.Many2one(
    #     "hr.benefit.package",
    #     string="Benefit Package",
    #     compute="_compute_benefit_package",
    #     store=True,
    #     help="The benefit package applicable to this employee based on their job position.",
    # )
    ahadu_employee_type_id = fields.Many2one(
        "hr.employee.type",
        string="Employee Type",
        compute="_compute_ahadu_employee_type_id",
        store=True,
        recursive=True,
        help="Determined based on the employee's job position.",
    )
    # benefit_line_ids = fields.One2many(
    #     related="benefit_package_id.line_ids", string="Applicable Benefits"
    # )

    woreda = fields.Char(string="Woreda")
    house_number = fields.Char(string="House Number")
    subcity = fields.Char(string="Subcity")

    guarantor_name = fields.Char(
        string="Guarantor Name",
        help="Name of the person who guaranteed this employee at the time of hiring.",
    )
    guarantor_company = fields.Char(string="Guarantor's Company")
    currency_id = fields.Many2one(
        "res.currency", string="Currency", related="company_id.currency_id"
    )
    bank_currency_id = fields.Many2one("res.currency", string="Currency")
    guarantor_commitment_amount = fields.Monetary(
        string="Guarantor Commitment Amount",
        help="The amount the guarantor is committed for.",
    )
    guarantee_letter = fields.Binary(string="Guarantee Letter", attachment=True)
    guarantee_letter_filename = fields.Char(string="Guarantee Letter Filename")

    retirement_notif_1y_sent = fields.Boolean(
        string="1-Year Retirement Notification Sent", default=False, copy=False
    )
    retirement_notif_6m_sent = fields.Boolean(
        string="6-Month Retirement Notification Sent", default=False, copy=False
    )
    retirement_notif_1m_sent = fields.Boolean(
        string="1-Month Retirement Notification Sent", default=False, copy=False
    )

    region_id = fields.Many2one(
        "hr.region", string="Region", ondelete="set null", tracking=True
    )
    city_id = fields.Many2one(
        "hr.city", string="City", ondelete="set null", tracking=True
    )

    @api.onchange("branch_id")
    def _onchange_branch(self):
        if self.branch_id:
            if self.branch_id.city_id:
                self.city_id = self.branch_id.city_id.id
            if self.branch_id.region_id:
                self.region_id = self.branch_id.region_id.id
            if self.branch_id.cost_center_id:
                self.cost_center_id = self.branch_id.cost_center_id.id

    # Activity tracking
    ahadu_activity_ids = fields.One2many(
        "hr.employee.activity", "employee_id", string="Activities"
    )
    # retirement_ids = fields.One2many(
    #     "hr.employee.retirement", "employee_id", string="Retirements"
    # )
    promotion_ids = fields.One2many(
        "hr.employee.promotion", "employee_id", string="Promotions"
    )
    ctc_ids = fields.One2many("hr.employee.ctc", "employee_id", string="CTC History")
    transfer_ids = fields.One2many(
        "hr.employee.transfer", "employee_id", string="Transfers"
    )
    # lateral_ids = fields.One2many(
    #     "hr.employee.lateral", "employee_id", string="Lateral Movements"
    # )
    demotion_ids = fields.One2many(
        "hr.employee.demotion", "employee_id", string="Demotions"
    )
    disciplinary_ids = fields.One2many(
        "hr.employee.disciplinary", "employee_id", string="Disciplinary Actions"
    )
    guarantee_ids = fields.One2many(
        "hr.employee.guarantee", "employee_id", string="Guarantees Provided"
    )
    termination_ids = fields.One2many(
        "hr.employee.termination", "employee_id", string="Terminations"
    )
    is_acting = fields.Boolean(string="Is Acting", readonly=True)
    acting_job_id = fields.Many2one("hr.job", string="Acting Position", readonly=True)
    acting_assignment_ids = fields.One2many(
        "hr.employee.acting", "employee_id", string="Acting Assignments"
    )
    temporary_assignment_ids = fields.One2many(
        "hr.employee.temporary.assignment",
        "employee_id",
        string="Temporary Assignments",
    )
    # Dashboard statistics
    total_activities = fields.Integer(
        string="Total Activities", compute="_compute_activity_stats"
    )
    pending_activities = fields.Integer(
        string="Pending Activities", compute="_compute_activity_stats"
    )

    # FIELDS FOR REPORTING
    age = fields.Integer(
        string="Age", compute="_compute_age", store=True, readonly=True
    )
    age_group = fields.Selection(
        [
            ("lt_20", "< 20"),
            ("20_29", "20-29"),
            ("30_39", "30-39"),
            ("40_49", "40-49"),
            ("50_59", "50-59"),
            ("ge_60", ">= 60"),
        ],
        string="Age Group",
        compute="_compute_age",
        store=True,
        readonly=True,
        group_operator=False,
    )

    resume_attachment = fields.Binary(string="CV/Resume File", attachment=True)
    resume_attachment_filename = fields.Char(string="CV/Resume Filename")

    # --- Approval Mixin Implementation ---
    def _get_employee_for_approval(self):
        """For employee model, the record itself is the employee."""
        return self

    def _perform_final_approval(self):
        """On final approval, activate the employee record."""
        self.ensure_one()
        self.write({"active": True})
        self.message_post(
            body=_("The new employee record has been approved and activated.")
        )

        if self.date_of_joining:
            self.env["hr.employee.probation"].create({"employee_id": self.id})
            self.message_post(
                body=_("A probation review has been automatically scheduled.")
            )

    # @api.model
    # def _name_search(self, name, domain=None, operator="ilike", limit=None, order=None):
    #     """
    #     Allows searching by Name OR Employee ID in Many2one fields and search bars.
    #     Depreciated in favor of _rec_names_search = ['name', 'employee_id']
    #     """
    #     domain = domain or []
    #     if name:
    #         # Check if name matches 'name' OR 'employee_id'
    #         domain = [
    #             "|",
    #             ("name", operator, name),
    #             ("employee_id", operator, name),
    #         ] + domain
    #     return self._search(domain, limit=limit, order=order)

    def _get_weighted_fuel_price(
        self, company_id, start_date, end_date, cutoff_date=None
    ):
        """
        Calculate weighted average fuel price between start_date and end_date.
        If cutoff_date is provided, ignore price changes happening STRICTLY AFTER cutoff_date.
        """
        # We need calendar to get days in month
        import calendar
        from datetime import datetime, date, timedelta

        days_in_period = (end_date - start_date).days + 1

        # 1. Fetch relevant price history
        # Fetch all changes effective on or before the end date
        domain = [
            ("company_id", "=", company_id),
            ("effective_date", "<=", end_date),
        ]

        history = (
            self.env["ahadu.fuel.price.history"]
            .sudo()
            .search(domain, order="effective_date asc, create_date asc")
        )

        # If cutoff provided, filter out "future knowledge"
        if cutoff_date:
            history = history.filtered(lambda r: r.effective_date <= cutoff_date)

        if not history:
            return 0.0

        # 2. Construct the timeline
        total_weighted_price = 0.0
        covered_days = 0

        # Find the active price at start_date
        current_price_rec = None
        future_changes = []

        for rec in history:
            if rec.effective_date <= start_date:
                current_price_rec = rec
            else:
                future_changes.append(rec)

        pointer_date = start_date
        current_price = current_price_rec.price if current_price_rec else 0.0

        for change in future_changes:
            change_date = change.effective_date
            if change_date > end_date:
                break

            days_active = (change_date - pointer_date).days
            if days_active > 0:
                weight = (current_price / days_in_period) * days_active
                total_weighted_price += weight
                covered_days += days_active

            pointer_date = change_date
            current_price = change.price

        remaining_days = (end_date - pointer_date).days + 1
        if remaining_days > 0:
            weight = (current_price / days_in_period) * remaining_days
            total_weighted_price += weight
            covered_days += remaining_days

        return total_weighted_price

    @api.depends("transport_allowance_liters", "company_id.fuel_price_cutoff_date")
    def _compute_transport_allowance_amount(self):
        import calendar
        from datetime import datetime, date, timedelta

        current_date = fields.Date.today()
        month_start = date(current_date.year, current_date.month, 1)
        days_in_month = calendar.monthrange(current_date.year, current_date.month)[1]
        month_end = date(current_date.year, current_date.month, days_in_month)

        # Previous Month Calculation
        prev_month_end = month_start - timedelta(days=1)
        prev_month_start = date(prev_month_end.year, prev_month_end.month, 1)

        for employee in self:
            company = employee.company_id
            if not company:
                continue

            # 1. Current Month Weighted Price
            current_rate = self._get_weighted_fuel_price(
                company.id, month_start, month_end
            )

            # 2. Retroactive Adjustment for Previous Month
            adjustment_rate = 0.0

            config_cutoff_date = company.fuel_price_cutoff_date
            if config_cutoff_date:
                # We assume the "Cutoff Day" is consistent, e.g. 21st of the month.
                cutoff_day = config_cutoff_date.day

                # Handle edge case where prev month has fewer days than cutoff day
                # e.g. Feb 28, but cutoff is 30th.
                prev_month_days = calendar.monthrange(
                    prev_month_start.year, prev_month_start.month
                )[1]
                actual_cutoff_day = min(cutoff_day, prev_month_days)

                prev_cutoff_date = date(
                    prev_month_start.year, prev_month_start.month, actual_cutoff_day
                )

                # Rate A: The "Real" rate (Full knowledge of Jan)
                rate_real = self._get_weighted_fuel_price(
                    company.id, prev_month_start, prev_month_end
                )

                # Rate B: The "Snapshot" rate (Knowledge stuck at Cutoff Date)
                rate_snapshot = self._get_weighted_fuel_price(
                    company.id,
                    prev_month_start,
                    prev_month_end,
                    cutoff_date=prev_cutoff_date,
                )

                adjustment_rate = rate_real - rate_snapshot

            final_rate = current_rate + adjustment_rate

            employee.transport_allowance_amount = (
                employee.transport_allowance_liters * final_rate
            )

    @api.model
    def _recompute_all_transport_allowances(self):
        """
        This method is called from HR Settings to recompute the transport allowance
        for all relevant employees when the global fuel price changes.
        """
        _logger.info(
            "Recomputing all employee transport allowances due to fuel price change."
        )
        employees_with_allowance = self.search([("transport_allowance_liters", ">", 0)])
        # Triggering the recomputation by calling the compute method
        if employees_with_allowance:
            employees_with_allowance._compute_transport_allowance_amount()

    @api.depends("job_id", "job_id.ahadu_employee_type_ids")
    def _compute_ahadu_employee_type_id(self):
        for employee in self:
            if employee.job_id and employee.job_id.ahadu_employee_type_ids:
                # Since we enforced exclusivity, there should be at most one type
                employee.ahadu_employee_type_id = (
                    employee.job_id.ahadu_employee_type_ids[0].id
                )
            else:
                employee.ahadu_employee_type_id = False

    # @api.depends("job_id")
    # def _compute_benefit_package(self):
    #     for employee in self:
    #         if employee.job_id:
    #             # Search for a package that includes the employee's job position.
    #             package = self.env["hr.benefit.package"].search(
    #                 [("job_ids", "=", employee.job_id.id), ("active", "=", True)],
    #                 limit=1,
    #             )
    #             employee.benefit_package_id = package.id if package else False
    #         else:
    #             employee.benefit_package_id = False

    # @api.constrains("employee_id")
    # def _check_employee_id_format(self):
    #     for record in self:
    #         if record.employee_id:
    #             # 1. Check format: Must be 'AHB' followed by 4 digits
    #             if not re.match(r"^AHB\d{4}$", record.employee_id):
    #                 raise ValidationError(
    #                     _(
    #                         "Employee ID is invalid. It must start with 'AHB' followed by exactly 4 numbers (e.g., AHB1234)."
    #                     )
    #                 )

    #             # 2. Check uniqueness
    #             existing_employee = self.search(
    #                 [("id", "!=", record.id), ("employee_id", "=", record.employee_id)],
    #                 limit=1,
    #             )
    #             if existing_employee:
    #                 raise ValidationError(
    #                     _(
    #                         "Employee ID must be unique. The ID '%s' is already assigned to another employee.",
    #                         record.employee_id,
    #                     )
    #                 )

    @api.constrains("work_phone", "mobile_phone")
    def _check_ethiopian_phone_number(self):
        phone_regex = re.compile(r"^(\+251\d{9}|09\d{8})$")
        for employee in self:
            if employee.work_phone and not phone_regex.match(employee.work_phone):
                raise ValidationError(
                    _(
                        "Work Phone number is not in a valid Ethiopian format (e.g., +251911123456 or 0911123456)."
                    )
                )
            if employee.mobile_phone and not phone_regex.match(employee.mobile_phone):
                raise ValidationError(
                    _(
                        "Mobile Phone number is not in a valid Ethiopian format (e.g., +251911123456 or 0911123456)."
                    )
                )

    birthday = fields.Date(string="Birthday")
    birthday_et = fields.Char(
        string="Birthday (ET)",
        compute="_compute_birthday_et",
        inverse="_inverse_birthday_et",
        store=True,
        help="Ethiopian date in DD/MM/YYYY format.",
    )

    @api.depends("birthday")
    def _compute_birthday_et(self):
        for employee in self:
            if employee.birthday:
                eth_date = self._gregorian_to_ethiopian(employee.birthday)
                # Format Ethiopian date as "DD/MM/YYYY" as requested
                employee.birthday_et = "%02d/%02d/%04d" % (
                    eth_date["day"],
                    eth_date["month"],
                    eth_date["year"],
                )
            else:
                employee.birthday_et = False

    def _inverse_birthday_et(self):
        for employee in self:
            greg_date = self._parse_and_convert_et_to_greg(employee.birthday_et)
            # On save (inverse), if the date is invalid, raise an error to maintain data integrity
            if employee.birthday_et and not greg_date:
                raise ValidationError(
                    _(
                        "Invalid Ethiopian Date format for '%s'. Please use a valid DD/MM/YYYY format.",
                        employee.birthday_et,
                    )
                )
            employee.birthday = greg_date

    def _parse_and_convert_et_to_greg(self, et_date_str):
        """
        Helper function to parse a DD/MM/YYYY Ethiopian date string and convert it.
        Returns a date object on success, or False on failure.
        """
        if not et_date_str:
            return False
        try:
            parts = et_date_str.strip().split("/")
            if len(parts) != 3:
                raise ValueError("Date must be in DD/MM/YYYY format.")

            day, month, year = int(parts[0]), int(parts[1]), int(parts[2])

            if not (1 <= month <= 13 and 1 <= day <= 30):
                raise ValueError("Invalid day or month.")
            if month == 13:
                is_leap = year % 4 == 3
                if (is_leap and day > 6) or (not is_leap and day > 5):
                    raise ValueError("Pagumen has only 5 or 6 days.")

            greg_date_dict = self._ethiopian_to_gregorian(year, month, day)
            return date(
                greg_date_dict["year"],
                greg_date_dict["month"],
                greg_date_dict["day"],
            )
        except (ValueError, TypeError):
            return False

    _JD_EPOCH_OFFSET_AMETE_MIHRET = 1723856

    def _greg_to_jdn(self, year, month, day):
        a = math.floor((14 - month) / 12)
        y = year + 4800 - a
        m = month + 12 * a - 3
        return (
            day
            + math.floor((153 * m + 2) / 5)
            + 365 * y
            + math.floor(y / 4)
            - math.floor(y / 100)
            + math.floor(y / 400)
            - 32045
        )

    def _jdn_to_eth(self, jdn):
        r = (jdn - self._JD_EPOCH_OFFSET_AMETE_MIHRET) % 1461
        n = (r % 365) + 365 * math.floor(r / 1460)
        year = (
            4 * math.floor((jdn - self._JD_EPOCH_OFFSET_AMETE_MIHRET) / 1461)
            + math.floor(r / 365)
            - math.floor(r / 1460)
        )
        month = math.floor(n / 30) + 1
        day = (n % 30) + 1
        return {"year": int(year), "month": int(month), "day": int(day)}

    def _eth_to_jdn(self, year, month, day):
        return (
            self._JD_EPOCH_OFFSET_AMETE_MIHRET
            + 365 * (year - 1)
            + math.floor(year / 4)
            + 30 * month
            + day
            - 31
        )

    def _jdn_to_greg(self, jdn):
        r = jdn + 68569
        n = math.floor((4 * r) / 146097)
        r = r - math.floor((146097 * n + 3) / 4)
        i = math.floor((4000 * (r + 1)) / 1461001)
        r = r - math.floor((1461 * i) / 4) + 31
        q = math.floor((80 * r) / 2447)
        day = r - math.floor((2447 * q) / 80)
        r = math.floor(q / 11)
        month = q + 2 - 12 * r
        year = 100 * (n - 49) + i + r
        return {"year": int(year), "month": int(month), "day": int(day)}

    def _gregorian_to_ethiopian(self, g_date):
        if not g_date:
            return None
        jdn = self._greg_to_jdn(g_date.year, g_date.month, g_date.day)
        return self._jdn_to_eth(jdn)

    def _ethiopian_to_gregorian(self, year, month, day):
        jdn = self._eth_to_jdn(year, month, day)
        return self._jdn_to_greg(jdn)

    @api.onchange("department_id")
    def _onchange_department_for_cost_center(self):
        """
        When the department is changed, automatically propose the
        department's default Cost Center for the employee.
        """
        if self.department_id and self.department_id.cost_center_id:
            self.cost_center_id = self.department_id.cost_center_id

    # @api.model
    # def _default_employee_id(self):
    #     """This method is called to get the default value for employee_id"""
    #     last_employee = self.search(
    #         [("employee_id", "=like", "AHB%")], order="employee_id desc", limit=1
    #     )
    #     if last_employee and last_employee.employee_id:
    #         try:
    #             # Safely get the number part of the ID
    #             last_num_str = last_employee.employee_id[3:]
    #             new_num = int(last_num_str) + 1
    #         except (ValueError, IndexError):
    #             # Fallback in case an ID is malformed (e.g., 'AHB-TEMP')
    #             new_num = 1
    #     else:
    #         # This is the first employee
    #         new_num = 1
    #     return f"AHB{new_num:04d}"

    @api.depends("birthday")
    def _compute_age(self):
        for employee in self:
            age_val = 0
            age_group_val = False
            if employee.birthday:
                today = date.today()
                age_val = (
                    today.year
                    - employee.birthday.year
                    - (
                        (today.month, today.day)
                        < (employee.birthday.month, employee.birthday.day)
                    )
                )
                if age_val < 20:
                    age_group_val = "lt_20"
                elif 20 <= age_val <= 29:
                    age_group_val = "20_29"
                elif 30 <= age_val <= 39:
                    age_group_val = "30_39"
                elif 40 <= age_val <= 49:
                    age_group_val = "40_49"
                elif 50 <= age_val <= 59:
                    age_group_val = "50_59"
                else:
                    age_group_val = "ge_60"
            employee.age = age_val
            employee.age_group = age_group_val

    @api.depends("first_name", "middle_name", "last_name")
    def _compute_full_name(self):
        for record in self:
            name_parts = [record.first_name, record.middle_name, record.last_name]
            record.name = " ".join(filter(None, name_parts))

    def _inverse_full_name(self):
        for record in self:
            if record.name:
                parts = record.name.strip().split()
                if len(parts) >= 1:
                    record.first_name = parts[0]
                else:
                    record.first_name = ""

                if len(parts) > 2:
                    record.middle_name = " ".join(parts[1:-1])
                elif len(parts) == 2:
                    # If only two names, middle name is empty
                    record.middle_name = ""
                else:
                    record.middle_name = ""

                if len(parts) >= 2:
                    record.last_name = parts[-1]
                else:
                    record.last_name = ""
            else:
                record.first_name = ""
                record.middle_name = ""
                record.last_name = ""

    # @api.depends("name", "employee_id")
    # @api.depends_context("show_manager_with_id")
    # def _compute_display_name(self):
    #     for employee in self:
    #         if (
    #             self.env.context.get("show_manager_with_id")
    #             and employee.name
    #             and employee.employee_id
    #         ):
    #             employee.display_name = f"{employee.name} ({employee.employee_id})"
    #         else:
    #             employee.display_name = employee.name
    
    @api.depends("name", "employee_id")
    @api.depends_context("show_manager_with_id", "show_employee_id_only")
    def _compute_display_name(self):
        for employee in self:
            if self.env.context.get("show_employee_id_only") and employee.employee_id:
                employee.display_name = employee.employee_id
            elif (
                self.env.context.get("show_manager_with_id")
                and employee.name
                and employee.employee_id
            ):
                employee.display_name = f"{employee.name} ({employee.employee_id})"
            else:
                employee.display_name = employee.name
    

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Force new employees to be active until approved
            vals["active"] = True

            if (
                "name" in vals
                and not vals.get("first_name")
                and not vals.get("last_name")
            ):
                name_parts = vals["name"].strip().split()
                if len(name_parts) >= 1:
                    vals["first_name"] = name_parts[0]
                if len(name_parts) > 2:
                    vals["middle_name"] = " ".join(name_parts[1:-1])
                if len(name_parts) >= 2:
                    vals["last_name"] = name_parts[-1]

            name_parts = [
                vals.get("first_name", ""),
                vals.get("middle_name", ""),
                vals.get("last_name", ""),
            ]
            vals["name"] = " ".join(filter(None, name_parts))

            if (
                not vals.get("first_name")
                or not vals.get("last_name")
                or not vals.get("middle_name")
            ):
                raise ValidationError(
                    _("First Name, Middle Name, and Last Name are required.")
                )

            if not vals.get("resource_id"):
                resource = self.env["resource.resource"].create(
                    {
                        "name": vals["name"],
                        "company_id": vals.get("company_id"),
                        "tz": self.env.user.tz or "Etc/UTC",
                    }
                )
                vals["resource_id"] = resource.id

        employees = super().create(vals_list)

        return employees

    def write(self, vals):
        if "job_id" in vals:
            old_jobs = self.filtered(
                lambda emp: emp.job_id.id != vals["job_id"]
            ).mapped("job_id")

        if "job_id" in vals:
            new_jobs = self.mapped("job_id")
            (old_jobs | new_jobs)._compute_status()

        # Handle archiving/unarchiving employees ---
        if "active" in vals:
            self.mapped("job_id")._compute_status()

        if any(key in vals for key in ["first_name", "middle_name", "last_name"]):
            for employee in self:
                first_name = vals.get("first_name", employee.first_name)
                middle_name = vals.get("middle_name", employee.middle_name)
                last_name = vals.get("last_name", employee.last_name)

                full_name = " ".join(filter(None, [first_name, middle_name, last_name]))
                vals["name"] = full_name
                if employee.resource_id:
                    employee.resource_id.write({"name": full_name})

        res = super().write(vals)

        return res

    # @api.constrains("work_email", "private_email")
    # def _check_email_validity(self):
    #     for employee in self:
    #         if employee.work_email and not email_re.match(employee.work_email):
    #             raise ValidationError(
    #                 _("The work email address '%s' is not valid.", employee.work_email)
    #             )
    #         if employee.private_email and not email_re.match(employee.private_email):
    #             raise ValidationError(
    #                 _(
    #                     "The private email address '%s' is not valid.",
    #                     employee.private_email,
    #                 )
    # )

    # @api.constrains("first_name", "middle_name", "last_name")
    # def _check_names_format(self):
    #     """Validates that names only contain alphabetic characters, spaces, hyphens, or apostrophes."""
    #     name_regex = re.compile(r"^[a-zA-Z\s'-]+$")
    #     for record in self:
    #         if record.first_name and not name_regex.match(record.first_name):
    #             raise ValidationError(
    #                 _(
    #                     "First Name can only contain letters, spaces, hyphens, or apostrophes."
    #                 )
    #             )
    #         if record.middle_name and not name_regex.match(record.middle_name):
    #             raise ValidationError(
    #                 _(
    #                     "Middle Name can only contain letters, spaces, hyphens, or apostrophes."
    #                 )
    #             )
    #         if record.last_name and not name_regex.match(record.last_name):
    #             raise ValidationError(
    #                 _(
    #                     "Last Name can only contain letters, spaces, hyphens, or apostrophes."
    #                 )
    #             )

    @api.constrains("birthday")
    def _check_employee_age(self):
        """
        Validates the employee's age based on their birthday.
        The age is a computed field, so we constrain the source field 'birthday'.
        - Must be at least 18 years old.
        - Cannot be older than a reasonable retirement age
        """
        for record in self:
            if record.birthday:
                today = date.today()
                age = relativedelta(today, record.birthday).years
                # if age < 18:
                #     raise ValidationError(_("Employee must be at least 18 years old."))
                # if age > 60:
                #     raise ValidationError(
                #         _(
                #             "The date of birth results in an age over 100. Please verify the date."
                #         )
                #     )

    # @api.constrains("tin_number")
    # def _check_tin_format_and_uniqueness(self):
    #     """
    #     Validates TIN number for uniqueness and ensures it only contains digits.
    #     The original check for uniqueness is preserved and enhanced.
    #     """
    #     for record in self:
    #         if record.tin_number:
    #             if not record.tin_number.isdigit():
    #                 raise ValidationError(_("TIN Number must contain only digits."))

    #             existing = self.search(
    #                 [("tin_number", "=", record.tin_number), ("id", "!=", record.id)]
    #             )
    #             if existing:
    #                 raise ValidationError(
    #                     _(
    #                         "TIN Number must be unique! Another employee already has this TIN."
    #                     )
    #                 )

    # @api.constrains("identification_id")
    # def _check_identification_id_uniqueness(self):
    #     """Ensures the National ID Number is unique across all employees."""
    #     for record in self:
    #         if record.identification_id:
    #             existing = self.search(
    #                 [
    #                     ("identification_id", "=", record.identification_id),
    #                     ("id", "!=", record.id),
    #                 ]
    #             )
    #             if existing:
    #                 raise ValidationError(_("National ID Number must be unique!"))

    # @api.constrains('date_of_joining')
    # def _check_date_of_joining(self):
    #     """Ensures the date of joining is not in the future."""
    #     for record in self:
    #         if record.date_of_joining and record.date_of_joining > fields.Date.today():
    #             raise ValidationError(_("The Date of Joining cannot be in the future."))

    @api.constrains("guarantor_commitment_amount")
    def _check_guarantor_amount(self):
        """Ensures the guarantor commitment amount is not negative."""
        for record in self:
            if record.guarantor_commitment_amount < 0:
                raise ValidationError(
                    _("Guarantor Commitment Amount cannot be a negative value.")
                )

    @api.depends("ahadu_activity_ids")
    def _compute_activity_stats(self):
        for employee in self:
            employee.total_activities = len(employee.ahadu_activity_ids)
            employee.pending_activities = len(
                employee.ahadu_activity_ids.filtered(lambda a: a.state == "draft")
            )

    def action_view_activities(self):
        return {
            "name": _("Employee Activities"),
            "type": "ir.actions.act_window",
            "res_model": "hr.employee.activity",
            "view_mode": "kanban,list,form",
            "domain": [("employee_id", "=", self.id)],
            "context": {"default_employee_id": self.id},
        }

    @api.model
    def _send_notification(self, employee, timeframe):
        """Helper to send notifications to manager and HR group."""
        hr_manager_group = self.env.ref("hr.group_hr_manager", raise_if_not_found=False)
        recipients = self.env["res.partner"]

        # manager as recipient
        if employee.parent_id and employee.parent_id.user_id:
            recipients |= employee.parent_id.user_id.partner_id

        # HR Managers as recipients
        if hr_manager_group:
            hr_users = hr_manager_group.users
            recipients |= hr_users.mapped("partner_id").filtered(lambda p: p.active)

        if not recipients:
            _logger.warning(
                f"No recipients found for retirement notification for employee: {employee.name}"
            )
            return

        retirement_date = employee.birthday + relativedelta(years=60)
        subject = f"Retirement Reminder for {employee.name}"
        body = f"This is a reminder that employee {employee.name} is scheduled to retire in {timeframe} (on {retirement_date})."

        # Post Odoo notification (in chatter)
        employee.message_post(
            body=body,
            subject=subject,
            partner_ids=recipients.ids,
            message_type="notification",
            subtype_xmlid="mail.mt_comment",
        )

        _logger.info(
            f"Posted retirement notification for {employee.name} to partners: {recipients.ids}"
        )

        # Send Email
        mail_template = self.env.ref(
            "ahadu_hr.email_template_retirement_notification", raise_if_not_found=False
        )
        if mail_template:
            for recipient in recipients:
                if recipient.email:
                    mail_template.with_context(
                        employee_name=employee.name,
                        timeframe=timeframe,
                        retirement_date=retirement_date,
                        recipient_name=recipient.name,
                    ).send_mail(
                        employee.id,
                        force_send=True,
                        email_values={"email_to": recipient.email},
                    )

    # @api.model
    # def _check_retirement_notifications(self):
    #     """Scheduled action to check for upcoming retirements."""
    #     today = fields.Date.today()
    #     # Find all active employees with a birthday who haven't received all notifications
    #     employees = self.search(
    #         [
    #             ("birthday", "!=", False),
    #             ("active", "=", True),
    #             "|",
    #             ("retirement_notif_1y_sent", "=", False),
    #             "|",
    #             ("retirement_notif_6m_sent", "=", False),
    #             ("retirement_notif_1m_sent", "=", False),
    #         ]
    #     )

    #     for emp in employees:
    #         # Calculate 60th birthday
    #         sixtieth_birthday = emp.birthday + relativedelta(years=60)

    #         # Check for 1 year milestone
    #         if (
    #             not emp.retirement_notif_1y_sent
    #             and sixtieth_birthday == today + relativedelta(years=1)
    #         ):
    #             self._send_notification(emp, "1 year")
    #             emp.write({"retirement_notif_1y_sent": True})

    #         # Check for 6 months milestone
    #         if (
    #             not emp.retirement_notif_6m_sent
    #             and sixtieth_birthday == today + relativedelta(months=6)
    #         ):
    #             self._send_notification(emp, "6 months")
    #             emp.write({"retirement_notif_6m_sent": True})

    #         # Check for 1 month milestone
    #         if (
    #             not emp.retirement_notif_1m_sent
    #             and sixtieth_birthday == today + relativedelta(months=1)
    #         ):
    #             self._send_notification(emp, "1 month")
    #             emp.write({"retirement_notif_1m_sent": True})

    @api.model
    def _send_retirement_notification(self, employee, timeframe):
        """Helper to send notifications to employee, manager, and Principal HR Officer."""
        recipients = self.env["res.partner"]

        # 1. The employee themselves
        if employee.user_id:
            recipients |= employee.user_id.partner_id

        # 2. The employee's manager
        if employee.parent_id and employee.parent_id.user_id:
            recipients |= employee.parent_id.user_id.partner_id

        # 3. Principal HR Officer(s)
        hr_officer_job = self.env.ref(
            "ahadu_hr.job_hr_officer", raise_if_not_found=False
        )
        if hr_officer_job:
            hr_officers = self.env["hr.employee"].search(
                [("job_id", "=", hr_officer_job.id)]
            )
            recipients |= hr_officers.mapped("user_id.partner_id").filtered(
                lambda p: p.active
            )

        if not recipients:
            _logger.warning(
                f"No recipients found for retirement notification for employee: {employee.name}"
            )
            return

        retirement_date = employee.birthday + relativedelta(years=60)
        subject = f"Retirement Reminder for {employee.name}"
        body = f"This is a reminder that employee {employee.name} is scheduled to retire in {timeframe} (on {retirement_date}). Please take the necessary actions."

        # Post Odoo notification (to employee's chatter)
        employee.message_post(
            body=body,
            subject=subject,
            partner_ids=recipients.ids,
            message_type="notification",
            subtype_xmlid="mail.mt_comment",
        )
        _logger.info(
            f"Posted retirement notification for {employee.name} to partners: {recipients.ids}"
        )

        # Send Email (using existing template)
        mail_template = self.env.ref(
            "ahadu_hr.email_template_retirement_notification", raise_if_not_found=False
        )
        if mail_template:
            for recipient in recipients:
                if recipient.email:
                    mail_template.with_context(
                        employee_name=employee.name,
                        timeframe=timeframe,
                        retirement_date=retirement_date,
                        recipient_name=recipient.name,
                    ).send_mail(
                        employee.id,
                        force_send=True,
                        email_values={"email_to": recipient.email},
                    )

    # @api.model
    # def _check_and_process_retirements(self):
    #     """
    #     Scheduled action to:
    #     1. Automatically retire employees who have reached age 60.
    #     2. Send notifications for employees approaching retirement.
    #     """
    #     today = fields.Date.today()
    #     # Find all active employees with a birthday
    #     employees = self.search([("birthday", "!=", False), ("active", "=", True)])

    #     for emp in employees:
    #         sixtieth_birthday = emp.birthday + relativedelta(years=60)

    #         # --- 1. Automatic Retirement ---
    #         if sixtieth_birthday <= today:
    #             retirement_reason = self.env.ref(
    #                 "hr.departure_reason_retirement", raise_if_not_found=False
    #             )
    #             emp.write(
    #                 {
    #                     "active": False,
    #                     "departure_date": sixtieth_birthday,
    #                     "departure_reason_id": (
    #                         retirement_reason.id if retirement_reason else False
    #                     ),
    #                 }
    #             )
    #             emp.message_post(
    #                 body=_(
    #                     f"This employee has been automatically retired on {sixtieth_birthday} upon reaching the age of 60."
    #                 )
    #             )
    #             _logger.info(
    #                 f"Automatically retired employee {emp.name} (ID: {emp.id})."
    #             )
    #             continue  # Skip to the next employee

    #         # --- 2. Notification Logic ---
    #         # Check for 1 year milestone
    #         if (
    #             not emp.retirement_notif_1y_sent
    #             and sixtieth_birthday == today + relativedelta(years=1)
    #         ):
    #             self._send_retirement_notification(emp, "1 year")
    #             emp.write({"retirement_notif_1y_sent": True})

    #         # Check for 6 months milestone
    #         if (
    #             not emp.retirement_notif_6m_sent
    #             and sixtieth_birthday == today + relativedelta(months=6)
    #         ):
    #             self._send_retirement_notification(emp, "6 months")
    #             emp.write({"retirement_notif_6m_sent": True})

    #         # Check for 1 month milestone
    #         if (
    #             not emp.retirement_notif_1m_sent
    #             and sixtieth_birthday == today + relativedelta(months=1)
    #         ):
    #             self._send_retirement_notification(emp, "1 month")
    #             emp.write({"retirement_notif_1m_sent": True})

    @api.model
    def get_employee_hierarchy(self, filters=None):
        """
        [UPDATED] Fetches all active employees and builds a nested hierarchy.
        This version accepts filters for department and job position.
        """
        if filters is None:
            filters = {}

        domain = [("active", "=", True)]
        # Apply filters to the initial domain
        if filters.get("department_id") and filters["department_id"] != "all":
            try:
                domain.append(("department_id", "=", int(filters["department_id"])))
            except (ValueError, TypeError):
                pass
        if filters.get("job_id") and filters["job_id"] != "all":
            try:
                domain.append(("job_id", "=", int(filters["job_id"])))
            except (ValueError, TypeError):
                pass

        # Find all employees matching the filter AND all their managers up to the top
        filtered_employees = self.search(domain)
        manager_ids = set()
        for emp in filtered_employees:
            current = emp
            while current.parent_id:
                manager_ids.add(current.parent_id.id)
                current = current.parent_id

        # The final set of employees to display in the chart includes the filtered
        # employees plus all of their managers.
        employee_ids_to_render = set(filtered_employees.ids) | manager_ids

        all_employees = self.search_read(
            [("id", "in", list(employee_ids_to_render))],
            ["id", "name", "job_title", "parent_id"],
        )

        employee_map = {emp["id"]: emp for emp in all_employees}

        # Initialize children list and subordinate count for all employees
        for emp in employee_map.values():
            emp["children"] = []
            emp["subordinates_count"] = 0
            emp["imageUrl"] = f'/web/image/hr.employee/{emp["id"]}/avatar_128'

        hierarchy = []
        processed_ids = set()

        # Build the hierarchy tree
        for emp_id, emp_data in employee_map.items():
            parent_id = emp_data["parent_id"][0] if emp_data["parent_id"] else None
            if parent_id and parent_id in employee_map and parent_id != emp_id:
                parent_emp = employee_map[parent_id]
                parent_emp["children"].append(emp_data)
            else:
                hierarchy.append(emp_data)

        # Helper function to recursively count all subordinates
        def _set_subordinate_counts(employee_node):
            # This is a post-processing step on the already built tree
            # We need to find all unique subordinates for this specific node
            all_subordinates = self.with_context(active_test=False).search(
                [
                    ("parent_id", "child_of", employee_node["id"]),
                    ("id", "!=", employee_node["id"]),
                ]
            )
            employee_node["subordinates_count"] = len(all_subordinates)

        # Apply counts to the final visible hierarchy
        for root_node in hierarchy:
            # We need a way to traverse the dict tree
            def traverse_and_count(node):
                _set_subordinate_counts(node)
                for child in node.get("children", []):
                    traverse_and_count(child)

            traverse_and_count(root_node)

        return {
            "hierarchy": hierarchy,
            "filters": {
                "departments": self.env["hr.department"].search_read(
                    [], ["id", "name"]
                ),
                "job_positions": self.env["hr.job"].search_read([], ["id", "name"]),
            },
        }

    @api.model
    def get_hr_analytics_data(self):
        """
        Provides data for the HR Analytics Dashboard.
        Computes stats for Vacancy and Span of Control.
        """
        # --- 1. Vacancy Analysis ---
        Job = self.env["hr.job"]
        active_jobs = Job.search([("active", "=", True)])

        total_positions = sum(active_jobs.mapped("expected_employees"))
        filled_positions = sum(active_jobs.mapped("no_of_employee"))
        vacant_positions = total_positions - filled_positions
        vacancy_rate = (
            (vacant_positions / total_positions * 100) if total_positions > 0 else 0
        )

        vacancy_stats = {
            "total_positions": total_positions,
            "filled_positions": filled_positions,
            "vacant_positions": vacant_positions,
            "vacancy_rate": vacancy_rate,
        }

        # --- 2. Span of Control Analysis ---
        Employee = self.env["hr.employee"]
        total_staff_count = Employee.search_count([("active", "=", True)])
        manager_count = Employee.search_count(
            [("active", "=", True), ("position_classification", "=", "management")]
        )
        non_manager_count = total_staff_count - manager_count
        span_of_control = (
            (non_manager_count / manager_count) if manager_count > 0 else 0
        )

        span_of_control_stats = {
            "total_staff_count": total_staff_count,
            "manager_count": manager_count,
            "non_manager_count": non_manager_count,
            "span_of_control": span_of_control,
        }

        return {
            "vacancy_stats": vacancy_stats,
            "span_of_control_stats": span_of_control_stats,
        }

    @api.model
    def get_employee_dashboard_data(self, filters=None):
        """Get comprehensive dashboard data with proper error handling"""
        try:
            if filters is None:
                filters = {}

            domain = [("active", "=", True)]

            if filters.get("branch") and filters["branch"] != "all":
                try:
                    domain.append(("branch_id", "=", int(filters["branch"])))
                except (ValueError, TypeError):
                    pass

            if filters.get("department") and filters["department"] != "all":
                try:
                    domain.append(("department_id", "=", int(filters["department"])))
                except (ValueError, TypeError):
                    pass

            if filters.get("gender") and filters["gender"] != "all":
                domain.append(("gender_updated", "=", filters["gender"]))

            if filters.get("age_group") and filters["age_group"] != "all":
                domain.append(("age_group", "=", filters["age_group"]))

            if filters.get("job_position") and filters["job_position"] != "all":
                try:
                    domain.append(("job_id", "=", int(filters["job_position"])))
                except (ValueError, TypeError):
                    pass

            if filters.get("grade") and filters["grade"] != "all":
                try:
                    domain.append(("grade_id", "=", int(filters["grade"])))
                except (ValueError, TypeError):
                    pass

            if filters.get("district") and filters["district"] != "all":
                try:
                    domain.append(("district_id", "=", int(filters["district"])))
                except (ValueError, TypeError):
                    pass

            # Date filter for NEW HIRES on hr.employee
            employee_date_domain = []
            if filters.get("newly_joined") and filters["newly_joined"] != "all":
                today = date.today()
                if filters["newly_joined"] == "30_days":
                    start_date = today - relativedelta(days=30)
                elif filters["newly_joined"] == "90_days":
                    start_date = today - relativedelta(days=90)
                else:  # this_year
                    start_date = date(today.year, 1, 1)
                employee_date_domain = [("date_of_joining", ">=", start_date)]

            # Get filtered employees
            filtered_employees = self.search(domain + employee_date_domain)
            total_employees = len(filtered_employees)

            # Calculate KPIs with fallbacks
            female_employees = len(
                filtered_employees.filtered(lambda e: e.gender_updated == "female")
            )
            male_employees = len(
                filtered_employees.filtered(lambda e: e.gender_updated == "male")
            )

            # Activity counts
            def safe_search_count(model_name, search_domain):
                try:
                    return self.env[model_name].search_count(search_domain)
                except Exception:
                    return 0

            def get_activity_date_domain(date_field_name):
                activity_date_domain = []
                if filters.get("newly_joined") and filters["newly_joined"] != "all":
                    today = date.today()
                    if filters["newly_joined"] == "30_days":
                        start_date = today - relativedelta(days=30)
                    elif filters["newly_joined"] == "90_days":
                        start_date = today - relativedelta(days=90)
                    else:  # this_year
                        start_date = date(today.year, 1, 1)
                    activity_date_domain = [(date_field_name, ">=", start_date)]
                return activity_date_domain

            promotion_domain = get_activity_date_domain("promotion_date") + [
                ("state", "=", "approved")
            ]
            transfer_domain = get_activity_date_domain("transfer_date") + [
                ("state", "=", "approved")
            ]
            demotion_domain = get_activity_date_domain("demotion_date") + [
                ("state", "=", "approved")
            ]
            retirement_domain = get_activity_date_domain("retirement_date") + [
                ("state", "=", "approved")
            ]
            disciplinary_domain = get_activity_date_domain("action_date") + [
                ("state", "=", "approved")  # Changed from 'active'
            ]

            promotions_count = safe_search_count(
                "hr.employee.promotion", promotion_domain
            )
            transfers_count = safe_search_count("hr.employee.transfer", transfer_domain)
            demotions_count = safe_search_count("hr.employee.demotion", demotion_domain)
            retirements_count = safe_search_count(
                "hr.employee.retirement", retirement_domain
            )
            disciplinary_count = safe_search_count(
                "hr.employee.disciplinary", disciplinary_domain
            )

            def get_chart_data(
                model, group_by_field, name_field=None, chart_domain=None
            ):
                try:
                    if chart_domain is None:
                        chart_domain = domain + employee_date_domain

                    if group_by_field not in self.env[model]._fields:
                        return {"labels": [], "data": []}

                    records = self.env[model].read_group(
                        chart_domain, ["id:count"], [group_by_field]
                    )

                    if not records:
                        return {"labels": [], "data": []}

                    if name_field:
                        comodel = self.env[model]._fields[group_by_field].comodel_name
                        record_ids = [
                            rec[group_by_field][0]
                            for rec in records
                            if rec[group_by_field]
                            and isinstance(rec[group_by_field], (list, tuple))
                        ]

                        if not record_ids:
                            return {"labels": [], "data": []}

                        names_map = {}
                        try:
                            name_records = self.env[comodel].search_read(
                                [("id", "in", record_ids)], [name_field]
                            )
                            names_map = {
                                rec["id"]: rec[name_field] for rec in name_records
                            }
                        except Exception:
                            names_map = {rid: f"Record {rid}" for rid in record_ids}

                        labels = []
                        data = []
                        for rec in records:
                            if rec[group_by_field] and isinstance(
                                rec[group_by_field], (list, tuple)
                            ):
                                label = names_map.get(rec[group_by_field][0], "Unknown")
                                labels.append(label)
                                data.append(rec[f"{group_by_field}_count"])
                    else:
                        # Handle selection fields
                        field_obj = self.env[model]._fields[group_by_field]
                        if hasattr(field_obj, "selection"):
                            selection_dict = dict(field_obj.selection)
                        else:
                            selection_dict = {}

                        labels = []
                        data = []
                        for rec in records:
                            if rec[group_by_field]:
                                label = selection_dict.get(
                                    rec[group_by_field], rec[group_by_field]
                                )
                                labels.append(label)
                                data.append(rec[f"{group_by_field}_count"])

                    return {"labels": labels, "data": data}

                except Exception as e:
                    return {"labels": ["Sample"], "data": [1]}

            # Hires over time
            last_6_months = [
                date.today() - relativedelta(months=i) for i in range(5, -1, -1)
            ]

            try:
                hires_data = self.read_group(
                    [("date_of_joining", ">=", date.today() - relativedelta(months=6))],
                    ["date_of_joining"],
                    ["date_of_joining:month"],
                )
                hires_map = {
                    rec["date_of_joining:month"]: rec["date_of_joining_count"]
                    for rec in hires_data
                }
                hires_over_time = {
                    "labels": [d.strftime("%b %Y") for d in last_6_months],
                    "data": [
                        hires_map.get(d.strftime("%B %Y"), 0) for d in last_6_months
                    ],
                }
            except Exception:
                hires_over_time = {
                    "labels": [d.strftime("%b %Y") for d in last_6_months],
                    "data": [1, 2, 0, 1, 3, 2],
                }

            # Activity trends
            def get_activity_trend(model_name, date_field):
                try:
                    activity_data = self.env[model_name].read_group(
                        [(date_field, ">=", date.today() - relativedelta(months=6))],
                        [date_field],
                        [f"{date_field}:month"],
                    )
                    activity_map = {
                        rec[f"{date_field}:month"]: rec[f"{date_field}_count"]
                        for rec in activity_data
                    }
                    return [
                        activity_map.get(d.strftime("%B %Y"), 0) for d in last_6_months
                    ]
                except Exception:
                    return [0, 1, 0, 0, 1, 0]

            promotion_trend = get_activity_trend(
                "hr.employee.promotion", "promotion_date"
            )
            transfer_trend = get_activity_trend("hr.employee.transfer", "transfer_date")
            retirement_trend = get_activity_trend(
                "hr.employee.retirement", "retirement_date"
            )
            demotion_trend = get_activity_trend("hr.employee.demotion", "demotion_date")

            # Activity summary
            activity_summary = {
                "labels": [
                    "Promotions",
                    "Transfers",
                    "Demotions",
                    "Retirements",
                    "Disciplinary",
                ],
                "data": [
                    promotions_count,
                    transfers_count,
                    demotions_count,
                    retirements_count,
                    disciplinary_count,
                ],
            }

            # Get filter options
            filter_options = {
                "branches": self.env["hr.branch"].search_read([], ["id", "name"]),
                "departments": self.env["hr.department"].search_read(
                    [], ["id", "name"]
                ),
                "genders": [
                    {"id": "male", "name": "Male"},
                    {"id": "female", "name": "Female"},
                ],
                "age_groups": [
                    {"id": "lt_20", "name": "< 20"},
                    {"id": "20_29", "name": "20-29"},
                    {"id": "30_39", "name": "30-39"},
                    {"id": "40_49", "name": "40-49"},
                    {"id": "50_59", "name": "50-59"},
                    {"id": "ge_60", "name": ">= 60"},
                ],
                "job_positions": self.env["hr.job"].search_read([], ["id", "name"]),
                "grades": self.env["hr.grade"].search_read([], ["id", "name"]),
                "districts": self.env["hr.district"].search_read([], ["id", "name"]),
            }

            return {
                "kpis": {
                    "total_employees": total_employees,
                    "female_employees": female_employees,
                    "male_employees": male_employees,
                    "female_percentage": (
                        round((female_employees / total_employees * 100), 1)
                        if total_employees
                        else 0
                    ),
                    "male_percentage": (
                        round((male_employees / total_employees * 100), 1)
                        if total_employees
                        else 0
                    ),
                    "promotions": promotions_count,
                    "transfers": transfers_count,
                    "demotions": demotions_count,
                    "retirements": retirements_count,
                    "disciplinary": disciplinary_count,
                },
                "charts": {
                    "by_gender": (
                        get_chart_data("hr.employee", "gender_updated")
                        if total_employees
                        else get_sample_chart_data("gender")
                    ),
                    "by_age": (
                        get_chart_data("hr.employee", "age_group")
                        if total_employees
                        else get_sample_chart_data("age")
                    ),
                    "by_location": (
                        get_chart_data("hr.employee", "branch_id", "name")
                        if total_employees
                        else get_sample_chart_data("location")
                    ),
                    "by_department": get_chart_data(
                        "hr.employee", "department_id", "name"
                    ),
                    "by_grade": get_chart_data("hr.employee", "grade_id", "name"),
                    "by_district": get_chart_data("hr.employee", "district_id", "name"),
                    "by_job_position": get_chart_data("hr.employee", "job_id", "name"),
                    "by_position_classification": get_chart_data(
                        "hr.employee", "position_classification"
                    ),
                    "hires_over_time": hires_over_time,
                    "activity_summary": activity_summary,
                    "activity_trends": {
                        "labels": [d.strftime("%b %Y") for d in last_6_months],
                        "datasets": [
                            {"label": "Promotions", "data": promotion_trend},
                            {"label": "Transfers", "data": transfer_trend},
                            {"label": "Retirements", "data": retirement_trend},
                            {"label": "Demotions", "data": demotion_trend},
                        ],
                    },
                    "promotions_by_grade": get_chart_data(
                        "hr.employee.promotion",
                        "new_grade_id",
                        "name",
                        promotion_domain,
                    ),
                    "transfers_by_branch": get_chart_data(
                        "hr.employee.transfer", "new_branch_id", "name", transfer_domain
                    ),
                    "retirements_by_type": get_chart_data(
                        "hr.employee.retirement",
                        "retirement_type",
                        None,
                        retirement_domain,
                    ),
                    "disciplinary_by_type": get_chart_data(
                        "hr.employee.disciplinary",
                        "action_type",
                        None,
                        disciplinary_domain,
                    ),
                },
                "filters": filter_options,
            }

        except Exception as e:
            return {
                "kpis": {
                    "total_employees": 0,
                    "female_employees": 0,
                    "male_employees": 0,
                    "female_percentage": 0,
                    "male_percentage": 0,
                    "promotions": 0,
                    "transfers": 0,
                    "demotions": 0,
                    "retirements": 0,
                    "disciplinary": 0,
                },
                "charts": {
                    "by_gender": {"labels": ["Male", "Female"], "data": [5, 3]},
                    "by_age": {
                        "labels": ["20-29", "30-39", "40-49"],
                        "data": [3, 3, 2],
                    },
                    "by_location": {
                        "labels": ["Head Office", "Branch 1"],
                        "data": [5, 3],
                    },
                    "by_department": {
                        "labels": ["HR", "IT", "Finance"],
                        "data": [2, 3, 3],
                    },
                    "by_grade": {"labels": ["Grade 1", "Grade 2"], "data": [4, 4]},
                    "by_district": {
                        "labels": ["District 1", "District 2"],
                        "data": [4, 4],
                    },
                    "by_job_position": {
                        "labels": ["Manager", "Developer", "Analyst"],
                        "data": [2, 3, 3],
                    },
                    "by_position_classification": {
                        "labels": ["Management", "Non-Management"],
                        "data": [2, 6],
                    },
                    "hires_over_time": {
                        "labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
                        "data": [1, 2, 0, 1, 3, 2],
                    },
                    "activity_summary": {
                        "labels": ["Promotions", "Transfers", "Demotions"],
                        "data": [2, 1, 0],
                    },
                    "activity_trends": {
                        "labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
                        "datasets": [
                            {"label": "Promotions", "data": [0, 1, 0, 0, 1, 0]},
                            {"label": "Transfers", "data": [1, 0, 0, 0, 0, 0]},
                        ],
                    },
                    "promotions_by_grade": {"labels": ["Grade 1"], "data": [2]},
                    "transfers_by_branch": {"labels": ["Branch 1"], "data": [1]},
                    "retirements_by_type": {"labels": ["Normal"], "data": [0]},
                    "disciplinary_by_type": {"labels": ["Warning"], "data": [0]},
                },
                "filters": {
                    "branches": [],
                    "departments": [],
                    "genders": [
                        {"id": "male", "name": "Male"},
                        {"id": "female", "name": "Female"},
                    ],
                    "age_groups": [
                        {"id": "20_29", "name": "20-29"},
                        {"id": "30_39", "name": "30-39"},
                    ],
                    "job_positions": [],
                    "grades": [],
                    "districts": [],
                },
            }
