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
                    ('date_to', '>=', slip.date_from),
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
            # Check Config: Selection for Payroll Attendance Mode
            mode = self.env['ir.config_parameter'].sudo().get_param('ahadu_payroll.payroll_attendance_mode') or 'standard'
            
            # Fetch all leaves for optimization
            all_leaves = self.env['hr.leave'].search([
                ('employee_id', '=', payslip.employee_id.id),
                ('state', '=', 'validate'),
                ('date_from', '<=', payslip.date_to),
                ('date_to', '>=', payslip.date_from),
            ])

            # Manual Absent Days from Approved Sheets
            manual_absent_dates = []
            if mode == 'manual':
                manual_sheets = self.env['ahadu.attendance.sheet'].search([
                    ('employee_id', '=', payslip.employee_id.id),
                    ('state', '=', 'approved'),
                    ('date_from', '<=', payslip.date_to),
                    ('date_to', '>=', payslip.date_from),
                ])
                manual_absent_dates = manual_sheets.mapped('line_ids.date')

            # Calculate Paid Days using unified logic
            total_days = (payslip.date_to - payslip.date_from).days + 1
            paid_days_count = payslip._get_paid_work_days(payslip.date_from, payslip.date_to)
            
            # Working days (excludes weekends & holidays) - strictly for UI reporting
            working_days_list = payslip._get_working_days()
            total_working_days = len(working_days_list)
            
            # Count detailed reasons for UI text
            days_with_attendance = 0
            leaves_taken_count = 0
            unauthorized_count = 0
            manual_absent_count = 0
            absent_day_records = []

            
            # Determine Employment Bounds
            contract_start = payslip.contract_id.date_start
            contract_end = payslip.contract_id.date_end
            
            # Check each working day
            for work_day in working_days_list:
                # SKIP days outside of active contract
                if (contract_start and work_day < contract_start) or (contract_end and work_day > contract_end):
                    continue
                    
                leave_for_day = payslip._get_leave_for_day(all_leaves, work_day)
                
                # Determine attendance based on mode
                is_present = False
                is_manual_absent = (mode == 'manual' and work_day in manual_absent_dates)
                
                if mode == 'automated':
                    if payslip._check_attendance_for_day(work_day):
                        is_present = True
                elif mode == 'manual':
                    # Manual: Present if no leave and NOT manually marked absent
                    if not leave_for_day and not is_manual_absent:
                        is_present = True
                else: # standard
                    if not leave_for_day:
                        is_present = True

                if is_present:
                    days_with_attendance += 1
                    continue

                # Employee was absent
                # Detailed tracking for reasons
                reason_type = 'unauthorized'
                if leave_for_day:
                    reason_type = 'leave'
                    leaves_taken_count += 1
                elif is_manual_absent:
                    reason_type = 'manual'
                    manual_absent_count += 1
                else:
                    unauthorized_count += 1
                
                absent_day_records.append({
                    'date': work_day,
                    'type': reason_type,
                    'leave': leave_for_day
                })
            
            # Calculate total absent
            total_absent = total_working_days - days_with_attendance
            
            # Build absence reason text
            absence_reasons = []
            count_unauth = 0
            count_manual = 0
            if absent_day_records:
                leave_types_count = {}
                
                for rec in absent_day_records:
                    if rec['type'] == 'leave':
                        name = rec['leave'].holiday_status_id.name
                        leave_types_count[name] = leave_types_count.get(name, 0) + 1
                    elif rec['type'] == 'manual':
                        count_manual += 1
                    else:
                        count_unauth += 1
                
                for l_type, count in sorted(leave_types_count.items()):
                    absence_reasons.append(f"{l_type}: {count} day{'s' if count > 1 else ''}")
                
                if count_manual > 0:
                    absence_reasons.append(f"Manual Absence: {count_manual} day{'s' if count_manual > 1 else ''}")
                
                if count_unauth > 0:
                    absence_reasons.append(f"Unauthorized Absence: {count_unauth} day{'s' if count_unauth > 1 else ''}")
            
            # Set field values
            payslip.working_days = total_working_days
            payslip.worked_days = round(paid_days_count, 1) # This matches the payroll logic
            payslip.leave_days = leaves_taken_count
            payslip.unauthorized_absent_days = unauthorized_count + manual_absent_count
            payslip.absent_days = total_days - paid_days_count
            payslip.absent_reason = '\n'.join(absence_reasons) if absence_reasons else 'No absences'

    def _get_worked_day_lines(self, domain=None):
        """
        Override to include manual absences and actual worked days in the 
        'Worked Days & Inputs' tab on the payslip.
        """
        res = super()._get_worked_day_lines(domain=domain)
        self.ensure_one()
        
        # 1. Total Calendar Days in Month
        total_days = (self.date_to - self.date_from).days + 1
        if total_days <= 0:
            return res
            
        # 2. Total Paid Days (Using unified logic)
        paid_days = self._get_paid_work_days(self.date_from, self.date_to)
        unpaid_days = total_days - paid_days
        
        # 3. Create/Update Worked Day Lines
        # Standard Odoo usually has a line with code 'WORK100' for presence. 
        # We will add a line for 'ABSENT' for the remaining days.
        
        if unpaid_days > 0:
            res.append({
                'name': _('Unpaid Absence (Manual/Automated)'),
                'sequence': 100,
                'code': 'ABSENT',
                'number_of_days': unpaid_days,
                'number_of_hours': unpaid_days * 8, # Assumption: 8h/day for display
                'contract_id': self.contract_id.id,
            })
            
        # Filter out standard WORK100 if we want to show our own 'PAID' line?
        # Actually, let's keep it clean and just add the 'PAID' line as a secondary indicator 
        # OR update the existing WORK100 if it exists.
        
        work_line = next((line for line in res if line['code'] == 'WORK100'), None)
        if work_line:
            work_line['number_of_days'] = paid_days
            work_line['number_of_hours'] = paid_days * 8
        else:
            res.append({
                'name': _('Worked Days (Paid)'),
                'sequence': 1,
                'code': 'WORK100',
                'number_of_days': paid_days,
                'number_of_hours': paid_days * 8,
                'contract_id': self.contract_id.id,
            })
            
        return res

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
        Now calculates tax impact first, then distributes the NET amount.
        """
        for slip in self:
            amount = 0.0
            tax = 0.0
            net = 0.0
            to_bal = 0.0
            to_sal = 0.0
            
            if slip.date_from and slip.date_to and slip.employee_id:
                # 1. Fetch Approved Calculation
                calculations = self.env['cash.indemnity'].search([
                    ('employee_id', '=', slip.employee_id.id),
                    ('state', 'in', ['approved', 'done']),
                    ('date_to', '>=', slip.date_from),
                    ('date_to', '<=', slip.date_to)
                ])
                amount = sum(c.total_amount for c in calculations)

            # 2. Calculate Tax Impact and Distribution
            if amount > 0:
                # --- NEW: Calculate Tax Impact ---
                # We need to know the tax on the total income with CI vs without CI
                # Base Taxable components (everything except CI)
                base_taxable = (slip._get_ahadu_basic_salary() - 
                                slip._get_ahadu_leave_deduction() - 
                                slip._get_ahadu_penalty_deduction() + 
                                slip._get_ahadu_taxable_transport() + 
                                slip._get_ahadu_representation() + 
                                slip._get_ahadu_taxable_hardship() + 
                                slip._get_ahadu_housing() + 
                                slip._get_ahadu_mobile() + 
                                slip._get_ahadu_lop_adjustment() + 
                                slip.overtime_amount)
                
                # Tax on base income
                tax_base = slip._get_ahadu_income_tax(base_taxable)
                # Tax on total income (including CI)
                tax_total = slip._get_ahadu_income_tax(base_taxable + amount)
                
                # The tax impact is the difference
                tax = tax_total - tax_base
                net = amount - tax

                # --- Distribution (Gap Logic) ---
                ci_account = self.env['hr.employee.bank.account'].search([
                    ('employee_id', '=', slip.employee_id.id),
                    ('account_type', '=', 'cash_indemnity')
                ], limit=1)
                
                current_balance = ci_account.balance if ci_account else 0.0
                
                # Gap Logic (Target 18,000 ETB)
                target = 18000.0
                gap = max(0.0, target - current_balance)
                
                if gap > 0:
                    # Priority 1: Fill the gap
                    fill_amount = min(net, gap)
                    
                    # Priority 2: Split remainder 50/50
                    remaining = net - fill_amount
                    split_part = remaining / 2.0
                    
                    to_bal = fill_amount + split_part
                    to_sal = split_part
                else:
                    # Balance already saturated, pure 50/50 split
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
            ('loan_type_id.is_payroll_deduction', '=', True),
        ]


        if loan_type_names:
            domain.append(('loan_type_id.name', 'in', loan_type_names))
            
        loans = self.env['hr.loan'].search(domain)
        
        total = 0.0
        for loan in loans:
            # For external loans, we check remaining amount
            # For manual loans, we check installment count
            if loan.is_external:
                if loan.remaining_amount > 0:
                    total += loan.monthly_installment
            elif loan.paid_installments < loan.installment_months:
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

    def _get_loan_details_by_type(self):
        """
        Returns a dictionary of loan deductions and their bank accounts, 
        grouped by loan type name.
        {
            'Personal Loan': {'amount': 500, 'account': '12345...'},
            ...
        }
        """
        self.ensure_one()
        details = {}
        
        loans = self.env['hr.loan'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'approved'),
            ('date_start', '<=', self.date_to),
            ('loan_type_id.is_payroll_deduction', '=', True),
        ])


        
        for loan in loans:
            # Check if active
            is_active = False
            if loan.is_external:
                if loan.remaining_amount > 0:
                    is_active = True
            elif loan.paid_installments < loan.installment_months:
                if self.date_to >= loan.date_start:
                    is_active = True
            
            if is_active:
                ltype = loan.loan_type_id.name
                amt = loan.monthly_installment
                acc = loan.bank_account_id.account_number or ''
                
                if ltype not in details:
                    details[ltype] = {'target_amount': 0.0, 'amount': 0.0, 'account': acc}
                
                details[ltype]['target_amount'] += amt
                # If multiple loans of same type, we take the one with account (or just the first one)
                if not details[ltype]['account'] and acc:
                    details[ltype]['account'] = acc
        
        # Now, fetch the actual calculated values from the payslip lines
        adv_actual = sum(self.line_ids.filtered(lambda l: l.code == 'ADV_LOAN').mapped('total'))
        pers_actual = sum(self.line_ids.filtered(lambda l: l.code == 'PERS_LOAN').mapped('total'))
        other_actual = sum(self.line_ids.filtered(lambda l: l.code == 'OTHER_LOAN').mapped('total'))

        # Distribute actuals proportionally based on targets
        adv_types = ['Emergency/Salary Advance Loan']
        pers_types = ['Personal Staff Loan']

        # Totals for proportional distribution
        adv_target_total = sum(d['target_amount'] for k, d in details.items() if k in adv_types)
        pers_target_total = sum(d['target_amount'] for k, d in details.items() if k in pers_types)
        other_target_total = sum(d['target_amount'] for k, d in details.items() if k not in adv_types and k not in pers_types)

        for ltype, data in details.items():
            target = data['target_amount']
            if target == 0:
                continue

            if ltype in adv_types:
                data['amount'] = round((target / adv_target_total) * adv_actual, 2) if adv_target_total else 0.0
            elif ltype in pers_types:
                data['amount'] = round((target / pers_target_total) * pers_actual, 2) if pers_target_total else 0.0
            else:
                data['amount'] = round((target / other_target_total) * other_actual, 2) if other_target_total else 0.0
        
        return details

    
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
        
        # Calculate 10% of Weighted Base Salary
        wage = self._get_ahadu_basic_salary()
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

    def _get_capped_amount(self, planned_amount, available_balance):
        """
        Helper to ensure a deduction does not exceed the available balance.
        Ensures Net Pay >= 0.
        """
        return max(0.0, min(planned_amount, available_balance))


    # ------------------------------------------------------
    # 1. BASIC & ALLOWANCE COMPUTATIONS
    # ------------------------------------------------------

    def _get_ahadu_basic_salary(self):
        """
        Returns the weighted monthly wage if there are salary changes (promotion/ctc).
        Otherwise returns the standard employee wage.
        Prorated by paid days.
        """
        self.ensure_one()
        segments = self._get_salary_and_job_segments()
        total_days = (self.date_to - self.date_from).days + 1
        
        if total_days == 0 or not segments:
            return round(self.employee_id.emp_wage or 0.0, 2)
            
        weighted_wage = 0.0
        for seg in segments:
            # Shift weight to use paid_days instead of all calendar_days
            weight = seg['paid_days'] / total_days
            weighted_wage += (seg['salary'] * weight)
            
        return round(weighted_wage, 2)

    def _get_ahadu_transport(self):
        """
        Returns transport allowance.
        Calculates prorated liters (Liter * Paid_Days / Total_Days) rounded to 2.
        Amount = Prorated Liters * Fuel Rate.
        """
        self.ensure_one()
        # 1. Check Liters 
        prorated_liters = self._get_ahadu_prorated_fuel_liters()
        if prorated_liters > 0:
            fuel_rate = self._get_weighted_fuel_rate()
            return round(prorated_liters * fuel_rate, 2)
        
        # 2. Fallback to Profile Amount ONLY if liters is 0 (Fixed amount case)
        base_amount = getattr(self.employee_id, 'transport_allowance_amount', 0.0)
        ratio = self._get_paid_days_ratio()
        return round(base_amount * ratio, 2)

    def _get_ahadu_prorated_fuel_liters(self):
        """
        Calculates fuel liters after attendance-based proration.
        Round to 2 decimal places.
        """
        self.ensure_one()
        # _get_weighted_fuel_liters already uses paid_days for proration
        raw_liters = self._get_weighted_fuel_liters()
        return round(raw_liters, 2)


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
        """Returns housing allowance from employee profile, prorated by attendance."""
        self.ensure_one()
        base_amount = self.employee_id.housing_allowance or 0.0
        ratio = self._get_paid_days_ratio()
        return round(base_amount * ratio, 2)

    def _get_ahadu_mobile(self):
        """Returns mobile allowance from employee profile, prorated by attendance."""
        self.ensure_one()
        base_amount = self.employee_id.mobile_allowance or 0.0
        ratio = self._get_paid_days_ratio()
        return round(base_amount * ratio, 2)

    def _get_ahadu_representation(self):
        """Returns representation allowance from employee profile, calculated as percentage of basic salary OR fixed amount, prorated by attendance."""
        self.ensure_one()
        # Priority: Fixed amount if > 0
        fixed_amount = getattr(self.employee_id, "representation_allowance_fixed", 0.0)
        if fixed_amount > 0:
            ratio = self._get_paid_days_ratio()
            return round(fixed_amount * ratio, 2)

        percentage = self.employee_id.representation_allowance or 0.0
        # Formula: (percentage / 100.0) * basic_salary
        # basic_salary is already prorated by attendance, so we don't multiply by ratio again
        base_amount = (percentage / 100.0) * self._get_ahadu_basic_salary()
        return round(base_amount, 2)

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

    def _get_ahadu_taxable_hardship(self):
        """
        Returns the taxable portion of the hardship allowance.
        Taxable Hardship = Max(0, Hardship Percentage - City Exemption Percentage) * Basic Salary
        """
        self.ensure_one()
        
        # 1. Get Employee's Total Hardship Percentage
        hardship_level = getattr(self.employee_id, 'hardship_allowance_level_id', False)
        if not hardship_level:
            return 0.0
            
        total_percentage = getattr(hardship_level, 'value_percentage', 0.0)
        if total_percentage <= 0:
            return 0.0
            
        # 2. Get Exemption Percentage for City
        exemption_percentage = 0.0
        city = getattr(self.employee_id, 'city_id', False)
        
        if city:
            config = self.env['ahadu.payroll.city.hardship.config'].search([
                ('city_id', '=', city.id)
            ], limit=1)
            
            if config:
                # The config stores the value like 30 for 30%
                exemption_percentage = config.non_taxable_percentage / 100.0

        # Taxable Percentage (minimum 0)
        taxable_percentage = max(0.0, total_percentage - exemption_percentage)
        
        if taxable_percentage <= 0:
            return 0.0
            
        # 3. Calculate Taxable Amount
        basic_salary = self._get_ahadu_basic_salary()
        taxable_amount = basic_salary * taxable_percentage
        
        return round(taxable_amount, 2)


    def _get_ahadu_benefit_amount(self, benefit_code):
        """
        [DEPRECATED] Benefits are now strictly on the employee profile.
        This method returns 0.0 to ensure consistency.
        """
        return 0.0


    def _get_ahadu_other_benefits(self):
        """Strictly 0.0 as all valid benefits are now mapped to specific profile fields."""
        return 0.0


    def _get_ahadu_benefit_amount_excluded(self, excluded_codes):
        """[DEPRECATED] Returns 0.0."""
        return 0.0


    def _get_ahadu_taxable_gross(self):
        """
        Calculates Taxable Salary & Benefits.
        Taxable = (Full Wage - Leave Deduction - Penalty) + Taxable Transport + Rep + Hardship + Housing + Mobile + LOP Adjustment
        """
        self.ensure_one()
        # Weighted Wage
        wage = self._get_ahadu_basic_salary()
        leave_deduction = self._get_ahadu_leave_deduction()
        penalty = self._get_ahadu_penalty_deduction()
        
        # Earned Basic = Weighted Wage - LOP Deduction - Penalty
        earned_basic = wage - leave_deduction - penalty
        
        taxable_trans = self._get_ahadu_taxable_gross_transport() if hasattr(self, '_get_ahadu_taxable_gross_transport') else self._get_ahadu_taxable_transport()
        rep = self._get_ahadu_representation()
        hardship = self._get_ahadu_taxable_hardship()
        housing = self._get_ahadu_housing()
        mobile = self._get_ahadu_mobile()
        lop_adj = self._get_ahadu_lop_adjustment()
        ci_allowance = self.cash_indemnity_allowance
        
        return earned_basic + taxable_trans + rep + hardship + housing + mobile + lop_adj + self.overtime_amount + ci_allowance

    # ------------------------------------------------------
    # 2. DEDUCTION COMPUTATIONS
    # ------------------------------------------------------

    def _get_working_days(self, date_from=None, date_to=None):
        """
        Calculate all working days in a given range or the payslip period.
        Excludes weekends (Saturday/Sunday) and public holidays.
        """
        from datetime import timedelta
        
        working_days = []
        current_date = date_from or self.date_from
        end_date = date_to or self.date_to
        
        if not current_date or not end_date:
            return []
            
        # Get public holidays for the period
        public_holidays = self._get_public_holidays()
        
        while current_date <= end_date:
            # Skip weekends (5=Saturday, 6=Sunday in Python)
            if current_date.weekday() not in [5, 6]:
                # Skip public holidays
                if current_date not in public_holidays:
                    working_days.append(current_date)
            
            current_date += timedelta(days=1)
        
        return working_days

    def _get_salary_and_job_segments(self):
        """
        Calculates salary and job segments within the payslip period.
        Constructs a timeline based on approved Promotions and CTC adjustments.
        """
        self.ensure_one()
        from datetime import timedelta
        
        date_from = self.date_from
        date_to = self.date_to
        employee = self.employee_id
        
        if not date_from or not date_to or not employee:
            return []

        # 1. Fetch relevant changes
        promotions = self.env['hr.employee.promotion'].search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'approved'),
            ('promotion_date', '>', date_from),
            ('promotion_date', '<=', date_to)
        ], order='promotion_date asc')
        
        ctcs = self.env['hr.employee.ctc'].search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'approved'),
            ('date', '>', date_from),
            ('date', '<=', date_to)
        ], order='date asc')
        
        # 2. Combine and sort change events
        events = []
        for p in promotions:
            events.append({
                'date': p.promotion_date,
                'salary': p.new_salary,
                'liters': getattr(p, 'new_transport_allowance_liters', 0.0),
                'job_id': p.new_job_id,
                'type': 'promotion',
                'prev_salary': p.current_salary,
                'prev_liters': getattr(p, 'current_transport_allowance_liters', 0.0),
                'prev_job': p.current_job_id
            })
        for c in ctcs:
            events.append({
                'date': c.date,
                'salary': c.new_wage,
                'liters': getattr(c, 'new_transport_allowance_liters', 0.0),
                'job_id': c.new_job_id or c.current_job_id,
                'type': 'ctc',
                'prev_salary': c.current_wage,
                'prev_liters': getattr(c, 'current_transport_allowance_liters', 0.0),
                'prev_job': c.current_job_id
            })
            
        # Sort by date
        events.sort(key=lambda x: x['date'])
        
        # 3. Handle overlapping changes on same day (take latest)
        unique_events = []
        if events:
            curr_date = events[0]['date']
            curr_event = events[0]
            for i in range(1, len(events)):
                if events[i]['date'] == curr_date:
                    curr_event = events[i] # Last one wins
                else:
                    unique_events.append(curr_event)
                    curr_date = events[i]['date']
                    curr_event = events[i]
            unique_events.append(curr_event)
            
        segments = []
        # 4. Construct Segments
        if not unique_events:
            total_paid = self._get_paid_work_days(date_from, date_to)
            cal_days = (date_to - date_from).days + 1
            segments.append({
                'start': date_from,
                'end': date_to,
                'salary': employee.emp_wage,
                'liters': getattr(employee, 'transport_allowance_liters', 0.0),
                'job_id': employee.job_id,
                'calendar_days': cal_days,
                'paid_days': total_paid,
            })
            return segments

        # Determine starting state from first event's previous values
        current_start = date_from
        current_salary = unique_events[0]['prev_salary']
        current_liters = unique_events[0]['prev_liters']
        current_job = unique_events[0]['prev_job']
        
        for event in unique_events:
            end_date = event['date'] - timedelta(days=1)
            if end_date >= current_start:
                cal_days = (end_date - current_start).days + 1
                paid_days = self._get_paid_work_days(current_start, end_date)
                segments.append({
                    'start': current_start,
                    'end': end_date,
                    'salary': current_salary,
                    'liters': current_liters,
                    'job_id': current_job,
                    'calendar_days': cal_days,
                    'paid_days': paid_days,
                })
            
            # Start next segment
            current_start = event['date']
            current_salary = event['salary']
            current_liters = event['liters']
            if event['job_id']:
                current_job = event['job_id']
                
        # Final segment
        if current_start <= date_to:
            cal_days = (date_to - current_start).days + 1
            paid_days = self._get_paid_work_days(current_start, date_to)
            segments.append({
                'start': current_start,
                'end': date_to,
                'salary': current_salary,
                'liters': current_liters,
                'job_id': current_job,
                'calendar_days': cal_days,
                'paid_days': paid_days,
            })
            
        return segments

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
            # SUPPORT BOTH NEW KEYS AND LEGACY NUMERIC KEYS
            if tier in ['full_pay', '100']:
                deduction_percentage = 0.0  # Full pay (no deduction)
            elif tier in ['half_pay', '50']:
                deduction_percentage = 0.5  # Half pay
            elif tier in ['no_pay', '0']:
                deduction_percentage = 1.0  # No pay
            else:
                _logger.warning(f"Unknown sick leave pay tier '{tier}' on leave {leave.id}. Defaulting to no deduction.")
                deduction_percentage = 0.0
        # Check Standard Unpaid Leave
        elif leave.holiday_status_id.unpaid:
            deduction_percentage = 1.0  # Full deduction
        else:
            # Paid leave (annual leave, etc.) - no deduction
            deduction_percentage = 0.0
        
        return daily_rate * deduction_percentage * half_day_modifier

    def _get_paid_work_days(self, date_from, date_to):
        """
        Calculates the number of days for which the employee should be paid within a specific range.
        Uses Calendar Days logic.
        """
        from datetime import timedelta
        self.ensure_one()
        
        # Total days in range (Calendar Days)
        total_days = (date_to - date_from).days + 1
        if total_days <= 0:
            return 0.0
            
        # Step 2: Get all leaves for the whole period (cached)
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

        paid_days = 0.0
        
        # Check Config
        mode = self.env['ir.config_parameter'].sudo().get_param('ahadu_payroll.payroll_attendance_mode') or 'standard'
        
        manual_absent_dates = []
        if mode == 'manual':
            manual_sheets = self.env['ahadu.attendance.sheet'].search([
                ('employee_id', '=', self.employee_id.id),
                ('state', '=', 'approved'),
                ('date_from', '<=', self.date_to),
                ('date_to', '>=', self.date_from),
            ])
            manual_absent_dates = manual_sheets.mapped('line_ids.date')

        # Determine Employment Bounds
        contract_start = self.contract_id.date_start
        contract_end = self.contract_id.date_end
        
        curr_date = date_from
        while curr_date <= date_to:
            # 1. Skip days outside of employment
            if (contract_start and curr_date < contract_start) or (contract_end and curr_date > contract_end):
                curr_date += timedelta(days=1)
                continue
            
            # 2. Check for Leaves FIRST (Leave takes precedence over absence sheets)
            leave_for_day = self._get_leave_for_day(all_leaves, curr_date)
            if leave_for_day:
                deduction_factor = self._calculate_leave_deduction(leave_for_day, 1.0)
                paid_days += (1.0 - deduction_factor)
                curr_date += timedelta(days=1)
                continue
            
            # 3. Check for Absences based on Mode
            if mode == 'manual':
                if curr_date in manual_absent_dates:
                    # Manual Absence marked => Unpaid
                    pass
                else:
                    paid_days += 1.0
            elif mode == 'automated':
                if self._check_attendance_for_day(curr_date):
                    paid_days += 1.0
                else:
                    # No attendance record => Unpaid
                    pass
            else: # Standard mode
                # Assume present unless leave was found (checked above)
                paid_days += 1.0
            
            curr_date += timedelta(days=1)
        
        return paid_days

    def _get_paid_days_ratio(self):
        """
        Returns the ratio of paid calendar days to total calendar days in the month.
        Used for prorating benefits.
        """
        total_days = (self.date_to - self.date_from).days + 1
        if total_days <= 0:
            return 1.0
        
        paid_days = self._get_paid_work_days(self.date_from, self.date_to)
        return paid_days / total_days

    def _get_contract_days_ratio(self):
        """
        Returns the ratio of active contract days to total calendar days in the month.
        Ignores absences; only handles joining and leaving.
        """
        total_days = (self.date_to - self.date_from).days + 1
        if total_days <= 0:
            return 1.0
            
        contract_start = self.contract_id.date_start
        contract_end = self.contract_id.date_end
        
        # Determine overlap range
        start = max(self.date_from, contract_start) if contract_start else self.date_from
        end = min(self.date_to, contract_end) if contract_end else self.date_to
        
        if start > end:
            return 0.0
            
        active_days = (end - start).days + 1
        return active_days / total_days

    def _get_ahadu_leave_deduction(self):
        """
        Deduction logic shifted to _get_ahadu_basic_salary to return the 'Calculated Balance'.
        Returns 0.0 here to avoid double deduction in the LOP_LEAVE rule.
        """
        return 0.0

    def _get_weighted_fuel_rate(self):
        """Calculate weighted average fuel rate for the payslip period"""
        self.ensure_one()
        date_from = self.date_from
        date_to = self.date_to
        
        # 1. Fetch fuel price history that could affect this period
        # We need all changes that happened before or during the period.
        history = self.env['ahadu.fuel.price.history'].search([
            ('company_id', '=', self.company_id.id),
            ('effective_date', '<=', date_to)
        ], order='effective_date asc')
        
        if not history:
            # Fallback to global config parameter if no history exists
            return float(self.env['ir.config_parameter'].sudo().get_param('ahadu_hr.fuel_price_per_liter', default=0.0))
            
        # 2. Find the price active at the START of the period
        pre_history = self.env['ahadu.fuel.price.history'].search([
            ('company_id', '=', self.company_id.id),
            ('effective_date', '<', date_from)
        ], order='effective_date desc', limit=1)
        
        current_price = pre_history.price if pre_history else history[0].price
        current_start = date_from
        
        total_weighted_price = 0.0
        total_days = (date_to - date_from).days + 1
        
        if total_days <= 0:
            return current_price
            
        # 3. Process changes that occurred WITHIN the period
        for h in history.filtered(lambda x: x.effective_date >= date_from):
            # Period before this change (within our payslip date range)
            days = (h.effective_date - current_start).days
            total_weighted_price += current_price * days
            current_price = h.price
            current_start = h.effective_date
            
        # 4. Final period from last change to the end of the month
        days = (date_to - current_start).days + 1
        total_weighted_price += current_price * days
        
        return total_weighted_price / total_days

    def _get_weighted_fuel_liters(self):
        """Calculate weighted average fuel liters for the period"""
        self.ensure_one()
        segments = self._get_salary_and_job_segments()
        total_days = (self.date_to - self.date_from).days + 1
        
        if total_days == 0:
            return getattr(self.employee_id, 'transport_allowance_liters', 0.0)
            
        if not segments:
            base_liters = getattr(self.employee_id, 'transport_allowance_liters', 0.0)
            ratio = self._get_paid_days_ratio()
            return base_liters * ratio
            
        weighted_liters = 0.0
        for seg in segments:
            weight = seg.get('paid_days', 0) / total_days
            weighted_liters += (seg.get('liters', 0.0) * weight)
            
        return weighted_liters


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



    def compute_sheet(self):
        """
        Enforce a safeguard that the final NET amount cannot be negative.
        If deductions exceed earnings, cap the NET line at 0.
        """
        res = super(HrPayslip, self).compute_sheet()
        for slip in self:
            net_line = slip.line_ids.filtered(lambda l: l.code == 'NET')
            if net_line and net_line.total < 0:
                net_line.total = 0.0
        return res

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
                slip.employee_id.sudo().write({
                    'cost_sharing_amount': new_bal,
                    'cost_sharing_status': 'paid' if new_bal <= 0 else slip.employee_id.cost_sharing_status
                })
            
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
            
            # Send the email (Asynchronous / Background)
            template.send_mail(slip.id, force_send=False)
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
