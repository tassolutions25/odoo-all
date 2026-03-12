import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    # ------------------------------------------------------
    # ATTENDANCE TRACKING FIELDS
    # ------------------------------------------------------
    
    working_days = fields.Integer(
        string='Working Days',
        compute='_compute_attendance_fields',
        store=True,
        help="Total working days in the payslip period (excludes weekends and public holidays)"
    )
    
    worked_days = fields.Integer(
        string='Worked Days',
        compute='_compute_attendance_fields',
        store=True,
        help="Days with attendance records"
    )
    
    absent_days = fields.Integer(
        string='Absent Days',
        compute='_compute_attendance_fields',
        store=True,
        help="Total working days without attendance (Sum of Leave Days + Unauthorized Absences)"
    )
    
    leave_days = fields.Integer(
        string='Leave Days',
        compute='_compute_attendance_fields',
        store=True,
        help="Days covered by approved leave requests"
    )

    unauthorized_absent_days = fields.Integer(
        string='Unauthorized Absence',
        compute='_compute_attendance_fields',
        store=True,
        help="Working days with no attendance AND no approved leave"
    )
    
    absent_reason = fields.Text(
        string='Absence Reason',
        compute='_compute_attendance_fields',
        store=True,
        help="Detailed breakdown of absence reasons (leave types or unauthorized)"
    )



    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)

    overtime_amount = fields.Monetary(
        string='Overtime Amount',
        compute='_compute_overtime_amount',
        store=True,
        currency_field='currency_id',
        help="Total Approved Overtime Amount for the period"
    )

    @api.depends('employee_id', 'date_from', 'date_to')
    def _compute_overtime_amount(self):
        for slip in self:
            amount = 0.0
            if slip.employee_id and slip.date_from and slip.date_to:
                # Find APPROVED or DONE overtime calculations in the period
                overtimes = self.env['ahadu.overtime'].search([
                    ('employee_id', '=', slip.employee_id.id),
                    ('state', 'in', ['approved', 'done']),
                    ('date_from', '>=', slip.date_from),
                    ('date_to', '<=', slip.date_to)
                ])
                amount = sum(ot.total_overtime_amount for ot in overtimes)
            slip.overtime_amount = amount

    def _get_cbs_cost_center(self):
        """
        Determines the correct CBS cost center code for this payslip.
        - Head Office: 9999-XX (from department)
        - Branches: XXXX (from branch)
        """
        self.ensure_one()
        emp = self.employee_id
        
        # Priority 1: Check Department for HO-specific code (9999-XX)
        if emp.department_id and emp.department_id.cost_center_id:
            code = emp.department_id.cost_center_id.code
            if code and code.startswith('9999'):
                return code

        # Priority 2: Check Branch code
        if emp.branch_id and emp.branch_id.cost_center_id:
            return emp.branch_id.cost_center_id.code or 'N/A'

        return 'N/A'

    @api.depends('date_from', 'date_to', 'employee_id')
    def _compute_attendance_fields(self):
        """
        Compute attendance tracking fields: working_days, worked_days, absent_days, absent_reason.
        Also computes leave_days and unauthorized_absent_days for better reporting.
        """
        from datetime import datetime
        
        for payslip in self:
            # Check Config: If attendance based payroll is OFF, assume full attendance
            attendance_based = self.env['ir.config_parameter'].sudo().get_param('ahadu_payroll.attendance_based_payroll')
            
            if not payslip.date_from or not payslip.date_to or not payslip.employee_id:
                payslip.working_days = 0
                payslip.worked_days = 0
                payslip.absent_days = 0
                payslip.leave_days = 0
                payslip.unauthorized_absent_days = 0
                payslip.absent_reason = ''
                continue
            
            # Get working days (excludes weekends & holidays)
            working_days_list = payslip._get_working_days()
            total_working_days = len(working_days_list)
            
            # Count days
            days_with_attendance = 0
            leaves_taken_count = 0
            unauthorized_count = 0
            
            # Detailed tracking
            absent_day_records = []  # List of (date, leave_or_none) tuples
            
            # Get leaves for optimization
            all_leaves = self.env['hr.leave'].search([
                ('employee_id', '=', payslip.employee_id.id),
                ('state', '=', 'validate'),
                ('date_from', '<=', payslip.date_to),
                ('date_to', '>=', payslip.date_from),
            ])
            
            # Determine Employment Bounds
            contract_start = payslip.contract_id.date_start
            contract_end = payslip.contract_id.date_end
            
            # Check each working day
            for work_day in working_days_list:
                # SKIP days outside of active contract
                if (contract_start and work_day < contract_start) or (contract_end and work_day > contract_end):
                    continue
                    
                # Determine attendance
                has_attendance = False
                if attendance_based:
                    has_attendance = payslip._check_attendance_for_day(work_day)
                
                leave_for_day = payslip._get_leave_for_day(all_leaves, work_day)
                
                if attendance_based:
                    if payslip._check_attendance_for_day(work_day):
                        days_with_attendance += 1
                        continue # Present
                else:
                    # Not attendance based: Present if NO leave
                    if not leave_for_day:
                         days_with_attendance += 1
                         continue

                # Employee was absent (or assumed absent due to leave)
                absent_day_records.append((work_day, leave_for_day))
                
                if leave_for_day:
                    leaves_taken_count += 1
                else:
                    # Unauthorized only if attendance based. 
                    if attendance_based:
                         unauthorized_count += 1
            
            # Calculate total absent (Legacy field support)
            total_absent = total_working_days - days_with_attendance
            
            # Build absence reason text
            absence_reasons = []
            if absent_day_records:
                # Group absences by leave type
                leave_types_count = {}
                count_unauth = 0
                
                for day, leave in absent_day_records:
                    if leave:
                        leave_type_name = leave.holiday_status_id.name
                        leave_types_count[leave_type_name] = leave_types_count.get(leave_type_name, 0) + 1
                    else:
                        count_unauth += 1
                
                # Build text
                for leave_type, count in sorted(leave_types_count.items()):
                    absence_reasons.append(f"{leave_type}: {count} day{'s' if count > 1 else ''}")
                
                if count_unauth > 0:
                    absence_reasons.append(f"Unauthorized Absence: {count_unauth} day{'s' if count_unauth > 1 else ''}")
            
            # Set field values
            payslip.working_days = total_working_days
            payslip.worked_days = days_with_attendance
            payslip.leave_days = leaves_taken_count
            payslip.unauthorized_absent_days = unauthorized_count
            payslip.absent_days = total_absent
            payslip.absent_reason = '\n'.join(absence_reasons) if absence_reasons else 'No absences'

    # ------------------------------------------------------
    # LOP ADJUSTMENT FIELDS
    # ------------------------------------------------------
    
    lop_adjustment = fields.Float(
        string='LOP Adjustment (ETB)',
        digits=(16, 2),
        default=0.0,
        help="Manual adjustment to reverse previous LOP deductions (positive amount in ETB). "
             "Used for retrospective leave approvals or corrections."
    )
    
    lop_adjustment_reason = fields.Text(
        string='Adjustment Reason',
        help="Explain why this LOP adjustment is being made (required for audit trail)"
    )
    
    lop_adjustment_reference = fields.Char(
        string='Reference Payslip',
        help="Reference to the original payslip where LOP was applied (e.g., 'January 2024')"
    )
    
    # ------------------------------------------------------
    # CASH INDEMNITY
    # ------------------------------------------------------

    cash_indemnity_allowance = fields.Float(
        string='Cash Indemnity Allowance',
        compute='_compute_cash_indemnity_values',
        store=True,
        help="Full amount (usually 1500) if perfect attendance"
    )

    cash_indemnity_tax = fields.Float(
        string='Cash Indemnity Tax (35%)',
        compute='_compute_cash_indemnity_values',
        store=True
    )

    net_cash_indemnity = fields.Float(
        string='Net Cash Indemnity',
        compute='_compute_cash_indemnity_values',
        store=True,
        help="Allowance - Tax"
    )

    ci_to_balance = fields.Float(
        string='CI to Balance',
        compute='_compute_cash_indemnity_values',
        store=True,
        help="Amount to be added to Cash Indemnity Account"
    )

    ci_to_salary = fields.Float(
        string='CI to Salary',
        compute='_compute_cash_indemnity_values',
        store=True,
        help="Amount to be added to Salary Account"
    )

    @api.depends('worked_days', 'absent_days', 'contract_id', 'employee_id', 'date_from', 'date_to')
    def _compute_cash_indemnity_values(self):
        """
        Calculates Cash Indemnity by fetching Approved/Done 'cash.indemnity' records.
        """
        for slip in self:
            amount = 0.0
            tax = 0.0
            net = 0.0
            to_bal = 0.0
            to_sal = 0.0
            
            if slip.date_from and slip.date_to and slip.employee_id:
                # Fetch Approved Calculation
                calculations = self.env['cash.indemnity'].search([
                    ('employee_id', '=', slip.employee_id.id),
                    ('state', 'in', ['approved', 'done']),
                    ('date_from', '>=', slip.date_from),
                    ('date_to', '<=', slip.date_to)
                ])
                # Check for overlap or sum multiple? Usually one per month.
                amount = sum(c.total_amount for c in calculations)

            # --- Tax & Distribution (Existing Logic) ---
            if amount > 0:
                # Fetch configured tax rate (default 35%)
                tax_rate = float(self.env['ir.config_parameter'].sudo().get_param('ahadu_payroll.cash_indemnity_tax_rate', 35.0))
                tax = amount * (tax_rate / 100.0)
                net = amount - tax

                # Calculate Distribution
                ci_account = self.env['hr.employee.bank.account'].search([
                    ('employee_id', '=', slip.employee_id.id),
                    ('account_type', '=', 'cash_indemnity')
                ], limit=1)
                
                current_balance = ci_account.balance if ci_account else 0.0
                
                # Gap Logic
                target = 18000.0
                gap = max(0.0, target - current_balance)
                
                if gap > 0:
                    # Priority 1: Fill the gap
                    fill_amount = min(net, gap)
                    
                    # Priority 2: Split remainder
                    remaining = net - fill_amount
                    split_part = remaining / 2.0
                    
                    to_bal = fill_amount + split_part
                    to_sal = split_part
                else:
                    # Balance already saturated, pure split
                    split_part = net / 2.0
                    to_bal = split_part
                    to_sal = split_part
            
            slip.cash_indemnity_allowance = round(amount, 2)
            slip.cash_indemnity_tax = round(tax, 2)
            slip.net_cash_indemnity = round(net, 2)
            slip.ci_to_balance = round(to_bal, 2)
            slip.ci_to_salary = round(to_sal, 2)

    def _get_ahadu_lop_adjustment(self):
        """
        Return the manual LOP adjustment amount.
        
        Returns:
            float: Positive amount to credit back to employee for previous LOP deductions
        """
        self.ensure_one()
        return self.lop_adjustment or 0.0

    # ------------------------------------------------------
    # LOAN & SAVINGS DEDUCTIONS
    # ------------------------------------------------------
    
    def _get_active_deductions(self, deduction_type):
        """
        Get active deductions of a specific type for the employee.
        
        Args:
            deduction_type: 'loan', 'savings', 'credit_association', or 'other'
        
        Returns:
            recordset: Active deductions matching the type
        """
        self.ensure_one()
        return self.env['hr.employee.deduction'].search([
            ('employee_id', '=', self.employee_id.id),
            ('deduction_type', '=', deduction_type),
            ('state', '=', 'active'),
            '|',
            ('start_date', '=', False),
            ('start_date', '<=', self.date_to),
            '|',
            ('end_date', '=', False),
            ('end_date', '>=', self.date_from),
        ])
    
    
    def _get_ahadu_personal_loan_deduction(self):
        """Returns just Personal Loan amount for reporting."""
        self.ensure_one()
        deductions = self._get_active_deductions('personal_loan')
        return round(sum(d.monthly_amount for d in deductions), 2)
    
    def _get_ahadu_new_loan_deduction(self, loan_type_names=None):
        """
        Get total monthly installment from the hr.loan model.
        If loan_type_names is provided, filters by those type names.
        """
        self.ensure_one()
        domain = [
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'approved'),
            ('date_start', '<=', self.date_to),
        ]
        if loan_type_names:
            domain.append(('loan_type_id.name', 'in', loan_type_names))
            
        loans = self.env['hr.loan'].search(domain)
        
        total = 0.0
        for loan in loans:
            if loan.paid_installments < loan.installment_months:
                # Check if the payslip period corresponds to a period >= start_date
                if self.date_to >= loan.date_start:
                    total += loan.monthly_installment
        return round(total, 2)

    def _get_ahadu_advance_loan_deduction(self):
        """Deduction for Salary Advance / Emergency loans."""
        return self._get_ahadu_new_loan_deduction(['Emergency/Salary Advance Loan'])

    def _get_ahadu_personal_loan_deduction(self):
        """Deduction for Personal Staff loans."""
        return self._get_ahadu_new_loan_deduction(['Personal Staff Loan'])

    def _get_ahadu_other_loan_deduction(self):
        """Deduction for any other loan types."""
        self.ensure_one()
        all_loans = self._get_ahadu_new_loan_deduction()
        adv = self._get_ahadu_advance_loan_deduction()
        pers = self._get_ahadu_personal_loan_deduction()
        return round(all_loans - adv - pers, 2)
    
    def _get_ahadu_loan_deduction(self):
        """
        Legacy/General method. Returns total loan repayment.
        """
        return self._get_ahadu_new_loan_deduction()
    
    def _get_ahadu_savings_deduction(self):
        """
        Get total savings deductions for this payslip.
        
        Returns:
            float: Total monthly savings deduction amount
        """
        self.ensure_one()
        deductions = self._get_active_deductions('savings')
        return round(sum(d.monthly_amount for d in deductions), 2)
    
    def _get_ahadu_credit_association_deduction(self):
        """
        Get total credit association deductions for this payslip.
        
        Returns:
            float: Total monthly credit association deduction amount
        """
        self.ensure_one()
        deductions = self._get_active_deductions('credit_association')
        return round(sum(d.monthly_amount for d in deductions), 2)

    def _get_ahadu_cost_sharing_deduction(self):
        """
        Automated Cost Sharing Logic:
        Deducts 10% of Basic Salary (Full Month Wage) until the commitment is fully paid.
        """
        self.ensure_one()
        commitment = getattr(self.employee_id, 'cost_sharing_amount', 0.0)
        if commitment <= 0:
            return 0.0
        
        # 10% of Base Salary (Full Month Wage)
        # We use the raw wage here as the base for the commitment calculation, 
        # not the prorated salary, to ensure consistent debt repayment schedules.
        wage = self.employee_id.emp_wage or 0.0
        target_deduction = wage * 0.10
        
        # Cap by remaining commitment
        amount = min(target_deduction, commitment)
        return round(amount, 2)
    
    def _get_ahadu_other_deduction(self):
        """
        Get total other deductions for this payslip.
        
        Returns:
            float: Total monthly other deduction amount
        """
        self.ensure_one()
        deductions = self._get_active_deductions('other')
        return round(sum(d.monthly_amount for d in deductions), 2)

    def _get_ahadu_penalty_deduction(self):
        """
        Get total penalty deduction for this payslip.
        Penalty is calculated as a percentage of (Wage - LOP Deduction).
        
        Returns:
            float: Total penalty deduction amount
        """
        self.ensure_one()
        deductions = self._get_active_deductions('penalty')
        
        # Base for penalty = Prorated Basic Salary
        penalty_base = self._get_ahadu_basic_salary()
        
        total_penalty = 0.0
        for d in deductions:
            if d.penalty_percentage:
                total_penalty += (d.penalty_percentage / 100.0) * penalty_base
        return round(total_penalty, 2)

    # ------------------------------------------------------
    # 1. BASIC & ALLOWANCE COMPUTATIONS
    # ------------------------------------------------------

    def _get_ahadu_basic_salary(self):
        """
        Returns the full monthly wage from the custom employee field.
        Proration/LOP is now handled explicitly in the 'LOP_LEAVE' rule.
        """
        self.ensure_one()
        return round(self.employee_id.emp_wage or 0.0, 2)

    def _get_ahadu_transport(self):
        """
        Returns transport allowance.
        Uses 'transport_allowance_amount' from ahadu_hr module.
        Prorated based on attendance.
        """
        self.ensure_one()
        # Fallback to 0.0 if field doesn't exist (though it should)
        base_amount = getattr(self.employee_id, 'transport_allowance_amount', 0.0)
        
        # Apply Proration
        ratio = self._get_paid_days_ratio()
        return round(base_amount * ratio, 2)

    def _get_ahadu_taxable_transport(self):
        """
        Returns taxable transport allowance based on employee's region.
        Taxable = Transport - Region Exemption
        """
        transport = self._get_ahadu_transport()
        exemption = self._get_region_transport_exemption()
        return max(0, transport - exemption)
    
    def _get_region_transport_exemption(self):
        """
        Get transport allowance exemption based on employee's region.
        
        Returns:
            float: Exemption amount in ETB (default 600.0 if no config found)
        """
        self.ensure_one()
        DEFAULT_EXEMPTION = 600.0
        
        # Get employee's region
        region = self.employee_id.region_id
        if not region:
            return DEFAULT_EXEMPTION
        
        # Look up region-specific configuration
        config = self.env['ahadu.payroll.region.config'].search([
            ('region_id', '=', region.id)
        ], limit=1)
        
        if config:
            return config.transport_allowance_exemption
        
        return DEFAULT_EXEMPTION

    def _get_ahadu_housing(self):
        """Returns housing allowance from Benefit Package."""
        return self._get_ahadu_benefit_amount(['HOUSING', 'HOUSE', 'HOUSING_ALLOWANCE'])

    def _get_ahadu_mobile(self):
        """Returns mobile allowance from Benefit Package."""
        return self._get_ahadu_benefit_amount(['MOBILE', 'MOB', 'CELL', 'MOBILE_ALLOWANCE'])

    def _get_ahadu_representation(self):
        """
        Returns representation allowance.
        Logic: 
        1. Percentage Based: (Basic Salary - Leave Deduction) * Representation %
           (User requested to preserve this specific formula)
        2. Fixed Amount: From Benefit Package (code REPRESENTATION) * Proration Ratio
        Returns sum of both.
        """
        self.ensure_one()
        
        # 1. Percentage Calculation (Original Formula)
        rep_percent = getattr(self.employee_id, 'representation_allowance', 0.0)
        percentage_amount = 0.0
        
        if rep_percent:
            basic = self._get_ahadu_basic_salary()
            leave_deduction = self._get_ahadu_leave_deduction()
            adjusted_basic = basic - leave_deduction
            percentage_amount = adjusted_basic * (rep_percent / 100.0)
            
        # 2. Benefit Package Calculation (Fixed Amount)
        # This returns the Prorated amount already via _get_ahadu_benefit_amount
        package_amount = self._get_ahadu_benefit_amount(['REPRESENTATION', 'REP'])
        
        return round(percentage_amount + package_amount, 2)

    def _get_ahadu_hardship(self):
        """
        Returns hardship allowance based on employee's hardship level.
        Fetches the hardship level from the employee profile and calculates
        the allowance as a percentage of the basic salary.
        
        Returns:
            float: Hardship allowance amount (prorated)
        """
        self.ensure_one()
        
        # Get the employee's hardship allowance level
        hardship_level = getattr(self.employee_id, 'hardship_allowance_level_id', False)
        
        if not hardship_level:
            return 0.0
        
        # Get the percentage value from the hardship level
        percentage = getattr(hardship_level, 'value_percentage', 0.0)
        
        if percentage <= 0:
            return 0.0
        
        # Calculate hardship allowance as percentage of basic salary
        basic_salary = self._get_ahadu_basic_salary()
        hardship_amount = basic_salary * (percentage)
        
        return round(hardship_amount, 2)


    def _get_ahadu_benefit_amount(self, benefit_code):
        """
        Generic method to calculate benefits from the package lines.
        Args:
            benefit_code (str or list): The benefit code(s) to look for.
        """
        self.ensure_one()
        employee = self.employee_id
        amount = 0.0
        
        # Ensure code is a list for easy checking
        if isinstance(benefit_code, str):
            target_codes = [benefit_code]
        else:
            target_codes = benefit_code

        for line in employee.benefit_package_id.line_ids:
            if line.benefit_type_id.code in target_codes:
                if line.value_type == 'fixed':
                    amount += line.value_fixed
                elif line.value_type == 'percentage':
                    amount += (line.value_percentage / 100.0) * employee.emp_wage
        
        # Apple Proration to Benefits
        ratio = self._get_paid_days_ratio()
        return round(amount * ratio, 2)

    def _get_ahadu_other_benefits(self):
        """Catch-all for benefits not explicitly defined."""
        self.ensure_one()
        employee = self.employee_id
        amount = 0.0
        # Exclude our new explicit fields
        processed_codes = [
            'HOUSING', 'HOUSE', 'HOUSING_ALLOWANCE',
            'HARDSHIP', 
            'REPRESENTATION', 
            'CASH_INDEMNITY', 
            'MOBILE', 'MOB', 'CELL', 'MOBILE_ALLOWANCE',
            'TRANS', 'TRANSPORT', 'TRANSPORT_ALLOWANCE'
        ]

        for line in employee.benefit_package_id.line_ids:
            if line.benefit_type_id.code not in processed_codes:
                if line.value_type == 'fixed' or line.value_type == 'in_kind':
                    amount += line.value_fixed
                elif line.value_type == 'percentage':
                    amount += (line.value_percentage / 100.0) * employee.emp_wage
        
        # Apply Proration
        ratio = self._get_paid_days_ratio()
    def _get_ahadu_taxable_gross(self):
        """
        Calculates Taxable Salary & Benefits.
        Taxable = (Full Wage - Leave Deduction - Penalty) + Taxable Transport + Rep + Hardship + Housing + Mobile + LOP Adjustment
        """
        self.ensure_one()
        wage = self.employee_id.emp_wage or 0.0
        leave_deduction = self._get_ahadu_leave_deduction()
        penalty = self._get_ahadu_penalty_deduction()
        
        # Earned Basic = Full Wage - LOP Deduction - Penalty
        earned_basic = wage - leave_deduction - penalty
        
        taxable_trans = self._get_ahadu_taxable_gross_transport() if hasattr(self, '_get_ahadu_taxable_gross_transport') else self._get_ahadu_taxable_transport()
        rep = self._get_ahadu_representation()
        hardship = self._get_ahadu_hardship()
        housing = self._get_ahadu_housing()
        mobile = self._get_ahadu_mobile()
        lop_adj = self._get_ahadu_lop_adjustment()
        
        return earned_basic + taxable_trans + rep + hardship + housing + mobile + lop_adj + self.overtime_amount

    # ------------------------------------------------------
    # 2. DEDUCTION COMPUTATIONS
    # ------------------------------------------------------

    def _get_working_days(self):
        """
        Calculate all working days in the payslip period (Full Month).
        Excludes weekends (Saturday/Sunday) and public holidays.
        
        Returns:
            list: List of date objects representing working days
        """
        from datetime import timedelta
        
        working_days = []
        current_date = self.date_from
        
        # Get public holidays for the period
        public_holidays = self._get_public_holidays()
        
        while current_date <= self.date_to:
            # Skip weekends (5=Saturday, 6=Sunday in Python)
            if current_date.weekday() not in [5, 6]:
                # Skip public holidays
                if current_date not in public_holidays:
                    working_days.append(current_date)
            
            current_date += timedelta(days=1)
        
        return working_days

    def _get_public_holidays(self):
        """
        Get public holidays from resource calendar.
        
        Returns:
            set: Set of date objects representing public holidays
        """
        from datetime import timedelta
        
        self.ensure_one()
        
        # Try to get holidays from employee's resource calendar
        if self.employee_id.resource_calendar_id:
            calendar = self.employee_id.resource_calendar_id
            
            # Get global leaves (public holidays) from calendar
            global_leaves = self.env['resource.calendar.leaves'].search([
                ('calendar_id', '=', calendar.id),
                ('date_from', '<=', self.date_to),
                ('date_to', '>=', self.date_from),
                ('resource_id', '=', False),  # Global leave (not employee-specific)
            ])
            
            holidays = set()
            for leave in global_leaves:
                # Extract date range
                current = leave.date_from.date()
                end = leave.date_to.date()
                while current <= end:
                    holidays.add(current)
                    current += timedelta(days=1)
            
            return holidays
        
        # Fallback - no public holidays
        return set()

    def _check_attendance_for_day(self, check_date):
        """
        Check if employee has any attendance record for the given date.
        
        Args:
            check_date (date): Date to check
        
        Returns:
            bool: True if employee has attendance, False otherwise
        """
        from datetime import datetime
        
        # Convert date to datetime range (full day)
        day_start = datetime.combine(check_date, datetime.min.time())
        day_end = datetime.combine(check_date, datetime.max.time())
        
        # Check for any attendance record (check-in) on this day
        attendance_count = self.env['hr.attendance'].search_count([
            ('employee_id', '=', self.employee_id.id),
            ('check_in', '>=', day_start),
            ('check_in', '<=', day_end),
        ])
        
        return attendance_count > 0

    def _get_leave_for_day(self, leaves, check_date):
        """
        Find the leave record that covers the given date.
        
        Args:
            leaves (recordset): hr.leave records to search
            check_date (date): Date to check
        
        Returns:
            hr.leave record or False
        """
        from datetime import datetime
        
        for leave in leaves:
            # Handle both date and datetime fields
            leave_start = leave.date_from.date() if isinstance(leave.date_from, datetime) else leave.date_from
            leave_end = leave.date_to.date() if isinstance(leave.date_to, datetime) else leave.date_to
            
            if leave_start <= check_date <= leave_end:
                return leave
        
        return False

    def _calculate_leave_deduction(self, leave, daily_rate):
        """
        Calculate deduction amount based on leave type.
        
        Leave Type Deduction Rules:
        - Annual Leave: 0% deduction (fully paid)
        - Paternity/Maternity/Marriage/Bereavement: 0% deduction (fully paid)
        - Sick Leave (Days 1-60): 0% deduction (100% paid)
        - Sick Leave (Days 61-120): 50% deduction (50% paid)
        - Sick Leave (Days 121+): 100% deduction (unpaid)
        - Leave Without Pay: 100% deduction
        - Half-day leaves: Apply 50% of the calculated deduction
        
        Args:
            leave (hr.leave): Leave record
            daily_rate (float): Daily salary rate
        
        Returns:
            float: Deduction amount for this day
        """
        deduction_percentage = 0.0
        
        # Handle half-day leave modifier
        # If is_half_day is True, we only deduct half of what we normally would
        half_day_modifier = 0.5 if getattr(leave, 'is_half_day', False) else 1.0
        
        # Check Sick Leave Tier (from custom hr module)
        tier = getattr(leave, 'sick_leave_pay_tier', False)
        
        if tier:
            if tier == '100':
                deduction_percentage = 0.0  # Full pay (no deduction)
            elif tier == '50':
                deduction_percentage = 0.5  # Half pay
            elif tier == '0':
                deduction_percentage = 1.0  # No pay
        # Check Standard Unpaid Leave
        elif leave.holiday_status_id.unpaid:
            deduction_percentage = 1.0  # Full deduction
        else:
            # Paid leave (annual leave, etc.) - no deduction
            deduction_percentage = 0.0
        
        return daily_rate * deduction_percentage * half_day_modifier

    def _get_paid_days_ratio(self):
        """
        Calculates the ratio of Paid Days to Total Working Days.
        Returns:
            float: Ratio between 0.0 and 1.0 (e.g., 0.15 for 3/20 days)
        """
        self.ensure_one()
        
        # Step 1: Get working days
        working_days = self._get_working_days()
        num_working_days = len(working_days)
        
        if num_working_days == 0:
            return 1.0 # Avoid division by zero, assume full pay if no working days defined
            
        # Step 2: Get all leaves
        leaves_cache = self._context.get('leaves_by_employee', {})
        if leaves_cache:
            all_leaves = leaves_cache.get(self.employee_id.id, [])
        else:
            all_leaves = self.env['hr.leave'].search([
                ('employee_id', '=', self.employee_id.id),
                ('state', '=', 'validate'),
                ('date_from', '<=', self.date_to),
                ('date_to', '>=', self.date_from),
            ])

        # Step 3: Calculate Paid Days
        paid_days = 0.0
        
        # Check Config
        attendance_based = self.env['ir.config_parameter'].sudo().get_param('ahadu_payroll.attendance_based_payroll')
        
        # Determine Employment Bounds
        contract_start = self.contract_id.date_start
        contract_end = self.contract_id.date_end
        
        for work_day in working_days:
            # Skip days outside of employment
            if (contract_start and work_day < contract_start) or (contract_end and work_day > contract_end):
                continue
                
            # Check Attendance
            if attendance_based:
                if self._check_attendance_for_day(work_day):
                    paid_days += 1.0
                    continue
            else:
                # If NOT attendance based, assume present (check leave below)
                pass

            # Check Approved Leave
            leave_for_day = self._get_leave_for_day(all_leaves, work_day)
            
            if leave_for_day:
                deduction_factor = self._calculate_leave_deduction(leave_for_day, 1.0)
                paid_days += (1.0 - deduction_factor)
            else:
                # No attendance needed (disabled) AND no leave => FULLY PAID
                if not attendance_based:
                    paid_days += 1.0
        
        return paid_days / num_working_days

    def _get_ahadu_leave_deduction(self):
        """
        Calculates the Loss of Pay (LOP) amount based on attendance/leave ratio.
        LOP = Full Wage * (1 - Paid Days Ratio)
        """
        self.ensure_one()
        wage = self.employee_id.emp_wage or 0.0
        ratio = self._get_paid_days_ratio()
        lop_amount = wage * (1.0 - ratio)
        return round(lop_amount, 2)

    def _get_ahadu_income_tax(self, taxable_income):
        """
        Calculates Ethiopian Income Tax based on Taxable Income.
        Uses configured Tax Brackets from 'ahadu.payroll.tax.bracket'.
        
        Args:
            taxable_income (float): The amount subject to tax
        """
        tax = 0.0
        
        # Fetch configurations (sorted by lower_bound asc)
        brackets = self.env['ahadu.payroll.tax.bracket'].search([
            ('active', '=', True)
        ], order='lower_bound asc')
        
        matched = False
        
        for bracket in brackets:
            # Check if income falls in this bracket
            # Case 1: Standard Range (Lower <= Income <= Upper)
            # Case 2: Open-ended Range (Lower <= Income, Upper is 0)
            
            lower = bracket.lower_bound
            upper = bracket.upper_bound
            
            is_match = False
            
            if upper > 0:
                if lower <= taxable_income <= upper:
                    is_match = True
            else:
                # 0 means infinity (e.g. 14001+)
                if taxable_income >= lower:
                    is_match = True
            
            if is_match:
                tax = (taxable_income * (bracket.rate / 100.0)) - bracket.deduction
                matched = True
                break # Found the bracket, stop searching
        
        # Fallback if no bracket matches (Should cover 0-600 if configured, but just in case)
        # Usually checking <= 600 is implicit in the first 0-2000 bracket with 0% rate.
        
        return round(max(0, tax), 2)



    @api.model_create_multi
    def create(self, vals_list):
        """
        Restrict Payroll Managers from creating payslips.
        Only Payroll Officers or System Administrators should create.
        """
        # Check if user is a Payroll Manager
        if self.env.user.has_group('payroll.group_payroll_manager'):
            # Check if user is NOT a System Admin (Superuser)
            if not self.env.user.has_group('base.group_system'):
                from odoo.exceptions import AccessError
                raise AccessError(_("Payroll Managers are restricted from creating Payslips. This action is reserved for Payroll Officers."))
                
        return super(HrPayslip, self).create(vals_list)



    def action_payslip_done(self):
        """
        Override to automate balance reductions on confirmation.
        1. Reduces Cost Sharing balance on employee record.
        2. Increments paid installments for active loans.
        """
        res = super(HrPayslip, self).action_payslip_done()
        for slip in self:
            # 1. Handle Cost Sharing Balance
            cost_sharing_line = slip.line_ids.filtered(lambda l: l.code == 'COST_SHARING')
            if cost_sharing_line and cost_sharing_line.total > 0:
                current_bal = getattr(slip.employee_id, 'cost_sharing_amount', 0.0)
                new_bal = max(0, current_bal - cost_sharing_line.total)
                slip.employee_id.sudo().write({'cost_sharing_amount': new_bal})
            
            # 2. Handle Loan Installments
            loan_codes = ['ADV_LOAN', 'PERS_LOAN', 'OTHER_LOAN', 'LOAN']
            loan_lines = slip.line_ids.filtered(lambda l: l.code in loan_codes)
            if loan_lines and sum(loan_lines.mapped('total')) > 0:
                # Legacy loans (from hr.employee.deduction)
                legacy_loans = slip._get_active_deductions('advance_loan') | slip._get_active_deductions('personal_loan')
                if legacy_loans:
                    legacy_loans.increment_paid_installment()
                
                # New loans (from hr.loan)
                new_loans = self.env['hr.loan'].search([
                    ('employee_id', '=', slip.employee_id.id),
                    ('state', '=', 'approved'),
                    ('date_start', '<=', slip.date_to),
                ])
                for loan in new_loans:
                    if loan.paid_installments < loan.installment_months:
                        if slip.date_to >= loan.date_start:
                            loan.increment_paid_installment()
            
            # 3. Handle Cash Indemnity Balance Update
            # If there is a "ci_to_balance" amount, add it to the cash indemnity account
            if slip.ci_to_balance > 0:
                ci_account = self.env['hr.employee.bank.account'].search([
                    ('employee_id', '=', slip.employee_id.id),
                    ('account_type', '=', 'cash_indemnity')
                ], limit=1)
                
                if ci_account:
                    # Increment the balance
                    # We use SUDO to ensure we can write even if the user has read-only access to bank accounts
                    new_ci_balance = ci_account.balance + slip.ci_to_balance
                    ci_account.sudo().write({'balance': new_ci_balance})
            
            # 4. Automatically send Payslip Email to Employee
            # This ensures emails are sent regardless of whether approved individually or in batch
            try:
                slip.action_send_payslip_email()
            except Exception as e:
                _logger.error(f"Failed to send payslip email for {slip.employee_id.name}: {str(e)}")
                
        return res

    def action_send_payslip_email(self):
        """
        Send the payslip PDF to the employee's work email.
        """
        template = self.env.ref('ahadu_payroll.mail_template_payslip_ahadu_v2', raise_if_not_found=False)
        if not template:
            _logger.error("Ahadu Payslip Mail Template not found!")
            return False
            
        for slip in self:
            if not slip.employee_id.work_email:
                _logger.warning(f"Skipping payslip email for {slip.employee_id.name}: No work email defined.")
                continue
            
            # Send the email
            template.send_mail(slip.id, force_send=True)
            _logger.info(f"Payslip email sent to {slip.employee_id.work_email} for employee {slip.employee_id.name}")
            
        return True


class HrPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    # These fields MUST be here for the dashboard to work
    date_from = fields.Date(related='slip_id.date_from', store=True, string='Date From')
    date_to = fields.Date(related='slip_id.date_to', store=True, string='Date To')
    department_id = fields.Many2one(related='slip_id.employee_id.department_id', store=True, string='Department')
    cost_center_id = fields.Many2one(related='slip_id.contract_id.cost_center_id', store=True, string='Cost Center')
    state = fields.Selection(related='slip_id.state', store=True, string='Status')
