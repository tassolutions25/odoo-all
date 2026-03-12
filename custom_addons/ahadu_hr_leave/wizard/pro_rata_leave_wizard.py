from odoo import models, fields, api, _
from datetime import date

class ProRataLeaveWizard(models.TransientModel):
    _name = 'ahadu.pro_rata.leave.wizard'
    _description = 'Pro-Rata Leave Calculator Wizard'

    employee_id = fields.Many2one(
        'hr.employee', string="Employee", readonly=True,
        default=lambda self: self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
    )
    date_of_joining = fields.Date(
        related='employee_id.date_of_joining',
        string="Joining Date", readonly=True
    )
    calculation_date = fields.Date(
        string="Calculate Accrual As Of",
        required=True,
        default=fields.Date.today
    )
    current_balance = fields.Float(
        string="Current Net Balance",
        compute='_compute_employee_stats',
        digits=(16, 2),
        readonly=True,
        help="The total number of annual leave days currently available (Approved Allocations - Leaves Taken)."
    )
    leaves_taken = fields.Float(
        string="Total Leaves Taken",
        compute='_compute_employee_stats',
        digits=(16, 2),
        readonly=True,
        help="Total annual leaves taken across all active allocations."
    )
    total_accrued_days = fields.Float(
        string="Predicted Net Balance", # <-- Renamed for clarity
        compute='_compute_total_accrued_days',
        digits=(16, 2),
        readonly=True
    )

    @api.depends('employee_id')
    def _compute_employee_stats(self):
        """Calculates current balance and leaves taken for the employee."""
        annual_leave_type = self.env.ref('ahadu_hr_leave.ahadu_leave_type_annual', raise_if_not_found=False)
        for wizard in self:
            if not wizard.employee_id or not annual_leave_type:
                wizard.current_balance = 0.0
                wizard.leaves_taken = 0.0
                continue

            # Find all validated annual leave allocations
            allocations = self.env['hr.leave.allocation'].search([
                ('employee_id', '=', wizard.employee_id.id),
                ('holiday_status_id', '=', annual_leave_type.id),
                ('state', '=', 'validate'),
            ])
            
            # effective_remaining_leaves is (Granted - Taken - Expired)
            wizard.current_balance = sum(allocations.mapped('effective_remaining_leaves'))
            wizard.leaves_taken = sum(allocations.mapped('leaves_taken'))

    @api.depends('employee_id', 'calculation_date', 'current_balance')
    def _compute_total_accrued_days(self):
        """
        [ENHANCED LOGIC]
        Calculates the predicted net balance of annual leave as of the 'calculation_date'.
        It takes the CURRENT net balance and adds the projected accrual from today
        until the calculation date.
        """
        for wizard in self:
            if not wizard.employee_id or not wizard.date_of_joining or not wizard.calculation_date:
                wizard.total_accrued_days = 0.0
                continue

            today = fields.Date.today()
            calculation_date = wizard.calculation_date
            
            # Start with the current net balance
            predicted_balance = wizard.current_balance

            # If the calculation date is in the future, add the projected accrual
            if calculation_date > today:
                doj = wizard.date_of_joining
                
                # --- Determine Entitlement for the projection period ---
                # We use today's service year boundaries to determine the rate.
                # (Assuming the rate doesn't change mid-projection for simplicity, 
                # or using the rate as of today)
                anniversary_this_year = doj.replace(year=today.year)
                if today < anniversary_this_year:
                    service_year_start = doj.replace(year=today.year - 1)
                else:
                    service_year_start = anniversary_this_year

                years_of_service = service_year_start.year - doj.year
                
                base_entitlement = {
                    'non_management': 16, 'manager': 17,
                    'director': 20, 'chief': 24
                }.get(wizard.employee_id.leave_entitlement_class, 16)
                
                additional_days = max(0, years_of_service)
                total_annual_entitlement = min(base_entitlement + additional_days, 30)
                daily_rate = total_annual_entitlement / 365.25

                # Calculate days from tomorrow until calculation_date
                future_days = (calculation_date - today).days
                future_accrual = future_days * daily_rate
                predicted_balance += future_accrual

            wizard.total_accrued_days = predicted_balance
