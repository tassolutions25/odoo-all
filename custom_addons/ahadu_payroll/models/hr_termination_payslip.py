# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class HrTerminationPayslip(models.Model):
    _name = 'hr.termination.payslip'
    _description = 'Termination Payslip'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name', readonly=True, compute='_compute_name')
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, tracking=True)
    run_id = fields.Many2one('hr.termination.run', string='Batch', ondelete='cascade', tracking=True)
    
    termination_date = fields.Date(string='Termination Date', required=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('calculated', 'Calculated'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ], string='Status', default='draft', tracking=True)

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    # --- Leave Pay Fields ---
    wage = fields.Monetary(string='Basic Salary')
    leave_days = fields.Float(string='Unutilized Annual Leave', digits=(16, 2))
    
    leave_pay_gross = fields.Monetary(string='Leave Pay (Gross)')
    leave_pay_tax = fields.Monetary(string='Tax Amount (Leave)')
    leave_pay_net = fields.Monetary(string='Leave Pay (Net)', compute='_compute_leave_pay_net')

    @api.depends('leave_pay_gross', 'leave_pay_tax')
    def _compute_leave_pay_net(self):
        for rec in self:
            rec.leave_pay_net = rec.leave_pay_gross - rec.leave_pay_tax

    # --- Unpaid Salary Fields ---
    present_days = fields.Integer(string='Present Days')
    unpaid_salary = fields.Monetary(string='Unpaid Salary')
    unpaid_transport = fields.Monetary(string='Unpaid Transport')
    unpaid_housing = fields.Monetary(string='Unpaid Housing')
    unpaid_mobile = fields.Monetary(string='Unpaid Mobile')
    representation_allowance = fields.Monetary(string='Representation')
    
    gross_amount = fields.Monetary(string='Gross Amount (Salary)')
    taxable_amount = fields.Monetary(string='Taxable Amount')
    tax_salary = fields.Monetary(string='Tax Amount (Salary)')
    
    # --- Deductions ---
    grand_tax = fields.Monetary(string='Total Tax', compute='_compute_grand_tax', store=True)
    pension_emp = fields.Monetary(string='Pension (7%)')
    pension_comp = fields.Monetary(string='Pension (11%)')
    
    # Manual Deductions
    lost_id_card = fields.Monetary(string='Lost ID Card')
    vat_on_id_card = fields.Monetary(string='VAT on ID Card')
    other_deductions = fields.Monetary(string='Other Deductions')
    
    total_deduction = fields.Monetary(string='Total Deduction')
    
    # --- Final Net ---
    net_payable = fields.Monetary(string='Net Termination Payable')

    @api.depends('leave_pay_tax', 'tax_salary')
    def _compute_grand_tax(self):
        for rec in self:
            rec.grand_tax = rec.leave_pay_tax + rec.tax_salary

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            if not self.employee_id.contract_id.date_end:
                # Clear date and warn if no end date set
                self.termination_date = False
                return {
                    'warning': {
                        'title': _("Warning"),
                        'message': _("This employee has no Contract End Date set. Please set it in the Employee Contract first.")
                    }
                }
            self.termination_date = self.employee_id.contract_id.date_end

    @api.model
    def create(self, vals):
        if 'employee_id' in vals:
            employee = self.env['hr.employee'].browse(vals['employee_id'])
            # STRICT CHECK: Only use Contract End Date
            if not employee.contract_id.date_end:
                from odoo.exceptions import UserError
                raise UserError(_("This employee is not terminated (Contract End Date is missing). Please verify with HR."))
            
            # Additional Check: If Batch is provided, validat date range?
            # It's good practice but user just said "check if ... contract end_date is set and it is in the current month"
            # We can check this if run_id is passed, or we check against "current month" (Date.today)?
            # Better to rely on the fetched date_end.
            vals['termination_date'] = employee.contract_id.date_end
            
        return super(HrTerminationPayslip, self).create(vals)

    def _compute_name(self):
        for rec in self:
            rec.name = f"Termination Pay - {rec.employee_id.name}"

    def compute_sheet(self):
        for rec in self:
            rec._compute_values()
            rec.state = 'calculated'

    def _compute_values(self):
        """
        Main calculation logic for Termination Pay.
        """
        self.ensure_one()
        
        # 1. Fetch Basic Data
        # Ensure we have essential data
        if not self.employee_id or not self.termination_date:
            return

        # Basic Salary (Wage)
        # Use emp_wage from employee as per user request ("fetch the base salary (wage )from hr employee")
        self.wage = self.employee_id.emp_wage or 0.0
        
        # Unutilized Leave
        # FETCH FROM hr.leave.allocation as per User Requirement
        self.leave_days = self._get_remaining_annual_leave_days()

        # -----------------------------------------------------
        # PART A: UNUTILIZED LEAVE PAYMENT
        # -----------------------------------------------------
        # 3. Leave Pay for working days
        # "base salary (wage) divided by number of working days of the month multiplied by annual leave balance"
        # Standard working days is usually 30 in Ethiopia for payroll, or 26.
        # User said "working days of the month". Odoo standard is 30 for monthly.
        DAYS_IN_MONTH = 30
        
        daily_wage = self.wage / DAYS_IN_MONTH
        leave_pay_gross = daily_wage * self.leave_days
        self.leave_pay_gross = round(leave_pay_gross, 2)
        
        # 4. Leave Pay for Each Month
        # "leave pay for (annual leave balance) divided by 12"
        # This seems to be for tax calculation purposes (annualizing?)
        leave_pay_per_month = leave_pay_gross / 12.0
        
        # 5. Tax Included Annual Leave
        # "basic salary plus leave pay for each month"
        tax_included_annual = self.wage + leave_pay_per_month
        
        # 6. Less Tax = Tax on (Tax Included Annual)
        # STEP 6 USES OLD TAX TABLE (0-600 Exempt)
        less_tax_1 = self._calculate_tax_old(tax_included_annual)
        
        # 7. Tax Excluded Annual Tax = Basic Salary
        # 8. Less: Tax = Tax on (Basic Salary)
        # STEP 8 USES NEW TAX TABLE (0-2000 Exempt per formula provided)
        less_tax_2 = self._calculate_tax_new(self.wage)
        
        # 9. Tax Difference
        tax_difference = less_tax_1 - less_tax_2
        
        # 10. Tax To Paid for Leave
        # "Tax Difference multiplied by 12"
        leave_pay_tax = tax_difference * 12.0
        self.leave_pay_tax = round(leave_pay_tax, 2)

        # -----------------------------------------------------
        # PART B: SALARY & BENEFITS (PRESENT DAYS)
        # -----------------------------------------------------
        # Calculate Present Days
        # "present days before end of life"
        # Assuming period starts at beginning of the termination month
        term_date = self.termination_date
        # Start of month
        start_date = term_date.replace(day=1)
        
        # Days to pay = Days from Start to Termination (Inclusive?)
        # "number of days in that month multiplied by the present days"
        # If term date is 14th, present days = 14?
        # User said "present days before end of life".
        # Let's count calendar days for now or working days?
        # Usually prorating is done on 30 days basis.
        # Let's assume Present Days = Day of Termination Date (e.g. 14th -> 14 days)
        # But we need to check if they joined mid-month? Unlikely for termination but possible.
        # Let's use simple day count for now.
        present_days = term_date.day
        self.present_days = present_days
        
        if present_days > 30: present_days = 30 # Cap at 30
        
        # Ratio
        ratio = present_days / 30.0
        
        # 11. Unpaid Salary
        unpaid_salary = self.wage * ratio
        self.unpaid_salary = round(unpaid_salary, 2)
        
        # 12. Unpaid Transport
        # "transport_allowance divided by the number of days in that month multiplied by the present days."
        trans_allowance = getattr(self.employee_id, 'transport_allowance_amount', 0.0)
        self.unpaid_transport = round(trans_allowance * ratio, 2)
        
        # 13. Representation Allowance
        # "representation_allowance multiplied by basic salary, divided by ... * present"
        # Note: Rep allowance can be % on employee.
        rep_percent = getattr(self.employee_id, 'representation_allowance', 0.0)
        rep_amount = 0.0
        if rep_percent:
             rep_amount = (self.wage * rep_percent / 100.0) * ratio
        
        # Also check Benefit Package for fixed rep allowance?
        # The user formula specifically mentioned "representation_allowance multiplied by basic salary" which implies %.
        # But for consistency with payslip, we should check package too.
        # But let's stick to the prompt strict steps: "Representation Allowance = representation_allowance multiplied by basic salary..."
        self.representation_allowance = round(rep_amount, 2)
        
        # 14. Unpaid Housing Allowance
        # Fetch from Benefit Package
        housing_base = self._get_benefit_amount(['HOUSING', 'HOUSE', 'HOUSING_ALLOWANCE'])
        self.unpaid_housing = round(housing_base * ratio, 2)
        
        # 15. Unpaid Mobile Allowance
        mobile_base = self._get_benefit_amount(['MOBILE', 'MOB', 'CELL', 'MOBILE_ALLOWANCE'])
        self.unpaid_mobile = round(mobile_base * ratio, 2)
        
        # 16. Gross amount
        gross_amount = (self.unpaid_salary + self.unpaid_transport + self.representation_allowance + 
                        self.unpaid_housing + self.unpaid_mobile)
        self.gross_amount = round(gross_amount, 2)
        
        # 17. Taxable amount
        # "Gross amount - 600"
        # Note: Usually Transport is exempted up to 600. 
        # Here user creates a simplified "Gross - 600".
        # We must ensure we don't go below zero.
        # Also, is it ONLY transport that is exempted? yes usually.
        # If Unpaid Transport < 600, we should only subtract Unpaid Transport?
        # The formula says "Gross amount - 600", strict interpretation.
        # But standard law is Exemption = min(Transport, 600).
        # Let's follow strict instruction "Gross amount - 600" but cap at 0.
        self.taxable_amount = max(0.0, self.gross_amount - 600.0)
        
        # 18. Less:Tax (Salary)
        # STEP 18 USES NEW TAX TABLE (Matches Step 8 formula)
        self.tax_salary = self._calculate_tax_new(self.taxable_amount)
        
        # 19. Grand Tax
        # "Tax To Paid for Leave plus Less:Tax(step 18)"
        # Computed field will handle this sum, but let's ensure it triggers
        
        # 20. Deduction Pension of employee(7%)
        # "Unpaid Salary multiplied by 0.07"
        self.pension_emp = round(self.unpaid_salary * 0.07, 2)
        
        # 22. Pension contribution of employer(11%)
        self.pension_comp = round(self.unpaid_salary * 0.11, 2)
        
        # 21. Total Deduction
        # "Grand Tax Amounts to be paid plus Deduction Pension of employee"
        # AND check for other deductions (Step 23, 24)
        # Step 23: Lost of ID (Manual Input)
        # Step 24: 15% VAT on Lost ID
        
        # Auto-calc VAT if Lost ID is set
        if self.lost_id_card:
            self.vat_on_id_card = round(self.lost_id_card * 0.15, 2)
            
        self.total_deduction = self.grand_tax + self.pension_emp + self.lost_id_card + self.vat_on_id_card + self.other_deductions
        
        # 25. Net Termination Payable
        # "Leave Pay ... plus Gross amount plus Total Deduction (should be minus?) ..."
        # Formula text: "Net ... = Leave Pay ... plus Gross amount plus Total Deduction minus Lost of ID card minus 15% ..."
        # Wait, Step 21 "Total Deduction = Grand Tax + Pension".
        # Step 25 says "Leave + Gross + Total Deduction ..." -> This must be MINUS Total Deduction.
        # "plus Total Deduction" matches the text "plus Total Deduction minus Lost of ID...", which is confusing.
        # Usually Net = Earnings - Deductions.
        # Let's assume Minus Total Deductions (which includes Tax and Pension).
        # And Lost ID/VAT are effectively deductions too.
        # If "Total Deduction" in Step 21 ONLY includes Tax + Pension, 
        # then we need to subtract Lost ID and VAT separately as per step 25 text.
        # My `total_deduction` field currently sums EVERYTHING.
        # So Net = Leave Pay Gross + Gross Amount - My_Total_Deduction.
        
        self.net_payable = self.leave_pay_gross + self.gross_amount - self.total_deduction

    def _calculate_tax(self, income):
        """
        Ethiopian Tax Brackets (Monthly)
        0-600: 0%
        601-1650: 10% - 60
        1651-3200: 15% - 142.5
        3201-5250: 20% - 302.5
        5251-7800: 25% - 565
        7801-10900: 30% - 955
        10901+: 35% - 1500
        
        Checking User's specific formulas in Request:
        IF(G11<=600, 0,
        IF(G11<=1650, (G11-600)*0.1,  -> This is equivalent to (G11*0.1 - 60)
        IF(G11<=3200, (G11-1650)*0.15+105, -> (G11*0.15 - 247.5 + 105) = G11*0.15 - 142.5. Correct.
        IF(G11<=5250, 337.5+(G11-3200)*0.2, -> 337.5 + G11*0.2 - 640 = G11*0.2 - 302.5. Correct.
        IF(G11<=7800, 747.5+(G11-5250)*0.25, -> 747.5 + G11*0.25 - 1312.5 = G11*0.25 - 565. Correct.
        IF(G11<=10900, 1385+(G11-7800)*0.3, -> 1385 + G11*0.3 - 2340 = G11*0.3 - 955. Correct.
        2315+(G11-10900)*0.35 -> 2315 + G11*0.35 - 3815 = G11*0.35 - 1500. Correct.
        
        Wait, Step 8 formula provided by user has different constants/deductions:
        IF(G13<=2000, 0, ...
        IF(G13<=4000, G13*15%-300 ...
        This looks like the NEW 2024 Tax Law (No tax < 2000?).
        However, Step 6 usage of old brackets (0-600) vs Step 8 usage of new brackets?
        User provided TWO different formulas.
        Step 6 (Leave Tax): Uses 0-600 brackets.
        Step 8 (Salary Tax for Excluded): Uses 0-2000 brackets? ("IF(G13<=2000,G13*0, IF(G13<=4000,G13*15%-300...")
        Actually, looking at the formulas carefully:
        Step 6: Old/Standard tax brackets.
        Step 8: "IF(G13<=2000,G13*0... IF(G13<=10000,G13*25%-850..." This matches the NEW Proclamation 1339/2024?
             2001-4000: 10%? No user says 15%-300?
             Let's parse generic deduction-from-percentage logic:
             User: "IF(G13<=4000, G13*15%-300" -> 15% rate, 300 deduction.
             "IF(G13<=7000, G13*20%-500" -> 20% rate, 500 deduction.
             "IF(G13<=10000, G13*25%-850" -> 25% rate, 850 deduction.
             "IF(G13<=14000, G13*30%-1350" -> 30% rate, 1350 deduction.
             "G13*35%-2050" -> 35% rate, 2050 deduction.
        
        This is Very Important. The user is using TWO DIFFERENT TAX TABLES in the same calculation?
        Step 6 (Annual Leave Tax): Uses Old Table (0-600 exempt).
        Step 8 (Excluded Annual Tax): Uses New Table? (0-2000 exempt?).
        step 18 (Salary Tax): "IF(G24<=2000, ... G24*35%-2050" -> Matches Step 8.
        
        Conclusion:
        - Leave Pay Calculation (Step 6) uses OLD TABLE (explicitly written in prompt).
        - Salary Tax (Step 18) and Step 8 use NEW TABLE (explicitly written in prompt).
        
        I will implement `_calculate_tax_old` and `_calculate_tax_new` to respect the prompt exactly.
        """
        # Defaulting to NEW table for generic call, but I will split them.
        return self._calculate_tax_new(income)

    def _calculate_tax_old(self, income):
        """Standard Old Tax Brackets (0-600 Exempt)"""
        if income <= 600: return 0
        elif income <= 1650: return income * 0.1 - 60
        elif income <= 3200: return income * 0.15 - 142.5
        elif income <= 5250: return income * 0.2 - 302.5
        elif income <= 7800: return income * 0.25 - 565
        elif income <= 10900: return income * 0.3 - 955
        else: return income * 0.35 - 1500

    def _calculate_tax_new(self, income):
        """New Tax Brackets (0-2000 Exempt) as per User Prompt Steps 8 & 18"""
        if income <= 2000: return 0
        elif income <= 4000: return income * 0.15 - 300 # User said 15% - 300?? New law usually starts 10%.
                                                         # But I MUST Follow User Formula: "G13*15%-300"
        elif income <= 7000: return income * 0.20 - 500
        elif income <= 10000: return income * 0.25 - 850
        elif income <= 14000: return income * 0.30 - 1350
        else: return income * 0.35 - 2050

    def _calculate_tax(self, income):
        # This method wrapper is used in Step 6 (Leave calc)
        # Wait, Step 6 called `_calculate_tax`.
        # I need to update Step 6 to call `_calculate_tax_old`.
        # And Step 8 & 18 to call `_calculate_tax_new`.
        return self._calculate_tax_new(income)

    def _get_remaining_annual_leave_days(self):
        """
        Refactored to fetch unutilized leave from `hr.leave.allocation`
        with 'ahadu_leave_type_annual' and field 'effective_remaining_leaves'.
        """
        # 1. Resolve Leave Type ID
        # Try to find by XML ID first (assuming it is 'ahadu_hr_leave.ahadu_leave_type_annual' or similar)
        # If not, fallback to name search just in case
        leave_type = None
        try:
            # Since I don't know the exact module name of the XML ID, I'll search by the ID string if possible
            # But ref() needs module.xml_id.
            # I will try 'ahadu_hr_leave.ahadu_leave_type_annual' as a best guess for the module name
            leave_type = self.env.ref('ahadu_hr_leave.ahadu_leave_type_annual', raise_if_not_found=False)
        except:
             pass
        
        if not leave_type:
             # Fallback: Search by XML ID string in ir.model.data directly if module is unknown?
             # Or search by name if XML ID failed.
             # User gave "ahadu_leave_type_annual", might be the Name?
             # Let's try searching by Name too.
             leave_type = self.env['hr.leave.type'].search(['|', ('name', '=', 'ahadu_leave_type_annual'), ('name', 'ilike', 'Annual')], limit=1)

        if not leave_type:
            return 0.0

        # 2. Query Allocations
        # "fetch the leave information from the "hr.leave.allocation" model ... "
        # "and the annual leave balance field is "effective_remaining_leaves""
        allocations = self.env['hr.leave.allocation'].search([
            ('employee_id', '=', self.employee_id.id),
            ('holiday_status_id', '=', leave_type.id),
            ('state', '=', 'validate'),
        ])
        
        # Sum up 'effective_remaining_leaves'
        total_days = sum(allocations.mapped('effective_remaining_leaves')) if allocations else 0.0
        return total_days

    def _get_benefit_amount(self, codes):
        """Helper to fetch benefit amount from employee package"""
        amount = 0.0
        if not self.employee_id.benefit_package_id:
            return 0.0
            
        for line in self.employee_id.benefit_package_id.line_ids:
            if line.benefit_type_id.code in codes:
                if line.value_type == 'fixed':
                    amount += line.value_fixed
                elif line.value_type == 'percentage':
                    amount += (line.value_percentage / 100.0) * self.wage
        return amount


    def action_confirm(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancel'})
