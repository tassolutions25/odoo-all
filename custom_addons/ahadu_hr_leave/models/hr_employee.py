from datetime import date, timedelta
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    date_of_joining = fields.Date(string="Date of Joining")

    # --- LEAVE ENTITLEMENT CLASS FIELD ---
    leave_entitlement_class = fields.Selection([
        ('non_management', 'Non-Management'),
        ('manager', 'Team Leader / Manager'),
        ('director', 'Director'),
        ('chief', 'C-Suite')
    ], string='Leave Entitlement Class', default='non_management', required=True,
       help="Defines the employee's category for annual leave entitlement calculations.")

    # ... existing fields ...
    first_sick_leave_date_in_spell = fields.Date(
        string="Start of Current Sickness Period",
        copy=False,
        help="The start date of the first sick leave in the current continuous period of sickness."
    )



    def action_open_pro_rata_wizard(self):
        self.ensure_one()
        if not self.date_of_joining:
            raise UserError(_("Cannot calculate pro-rata leave without a joining date for the employee."))

        return {
            'name': _('Calculate Pro-Rata Leave'),
            'type': 'ir.actions.act_window',
            'res_model': 'ahadu.pro_rata.leave.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_employee_id': self.id,
            }
        }
      
        
    @api.model
    def _cron_reset_sick_leave(self):
        """
        Daily cron job to reset sick leave allocations for employees whose
        sickness period has expired (1 year after the first sick leave).
        """
        _logger.info("Starting daily sick leave reset process...")
        today = fields.Date.today()
        sick_leave_type = self.env.ref('ahadu_hr_leave.ahadu_sick_leave_request', raise_if_not_found=False)
        if not sick_leave_type:
            return
            
        # Find all employees who have a 'first_sick_leave_date_in_spell' set
        employees_to_check = self.search([('first_sick_leave_date_in_spell', '!=', False)])
        
        for employee in employees_to_check:
            # Calculate the date when their sick leave period should reset
            reset_date = employee.first_sick_leave_date_in_spell + relativedelta(years=1)
            
            # If today is on or after the reset date, it's time to reset
            if today >= reset_date:
                _logger.info(f"Sick leave period for {employee.name} has expired. Resetting balance.")
                
                # Find their sick leave allocation
                allocation = self.env['hr.leave.allocation'].search([
                    ('employee_id', '=', employee.id),
                    ('holiday_status_id', '=', sick_leave_type.id),
                ], limit=1)
                
                if allocation:
                    # Reset the allocation back to 180 days
                    allocation.write({'number_of_days': 180})
                    
                # Clear the spell start date so a new period can begin
                employee.write({'first_sick_leave_date_in_spell': False})
 

    @api.model
    def _cron_daily_leave_accrual(self):
        """
        [DEFINITIVE, SIMPLE LOGIC] Calculates the total accrued leave for the
        CURRENT service year and sets the allocation value directly. This is robust
        and self-correcting.
        """
        _logger.info("Starting simple, state-based daily accrual process...")
        
        annual_leave_type = self.env.ref('ahadu_hr_leave.ahadu_leave_type_annual', raise_if_not_found=False)
        if not annual_leave_type:
            _logger.error("Annual Leave type not found. Skipping accrual.")
            return

        all_employees = self.search([('date_of_joining', '!=', False)])
        today = fields.Date.today()

        # Get accrual launch date from settings
        accrual_launch_date_str = self.env['ir.config_parameter'].sudo().get_param(
            'ahadu_hr_leave.accrual_launch_date', default=False
        )
        # Parse it as Datetime (as per the new setting type) and convert to Date for comparison
        accrual_launch_datetime = fields.Datetime.from_string(accrual_launch_date_str) if accrual_launch_date_str else None
        accrual_launch_date = accrual_launch_datetime.date() if accrual_launch_datetime else None

        for employee in all_employees:
            # [FIXED LOGIC] Use original DOJ for Service Year boundaries even if hired before launch
            doj = employee.date_of_joining
            
            # 1. Determine the current Service Year the employee is in based on DOJ
            # This ensures anniversaries and rollovers happen on their DOJ, not the Launch Date.
            anniversary_this_year = doj.replace(year=today.year)
            if today < anniversary_this_year:
                service_year_start = doj.replace(year=today.year - 1)
                years_of_service = (today.year - 1) - doj.year
            else:
                service_year_start = anniversary_this_year
                years_of_service = today.year - doj.year

            # Determine where to start the accrual count for THIS bucket
            # If the service year started BEFORE the launch date, we only accrue from the launch date.
            # If the service year started AFTER the launch date, we accrue from the service year start.
            accrual_start_point = max(accrual_launch_date, service_year_start) if accrual_launch_date else service_year_start

            # 2. Find or Create the Allocation Bucket for this service year
            # [BROADER SEARCH] Look for any pro-rata allocation for this service year.
            # We check for:
            # a) Correct date_from = service_year_start
            # b) Pinned to launch date = accrual_launch_date (The legacy bug)
            # c) Matching name pattern
            search_domain = [
                ('employee_id', '=', employee.id),
                ('holiday_status_id', '=', annual_leave_type.id),
                '|', '|',
                ('date_from', '=', service_year_start),
                ('date_from', '=', accrual_launch_date),
                ('name', '=', f"Annual Leave {service_year_start.year} for {employee.name}"),
            ]
            all_potential_allocs = self.env['hr.leave.allocation'].search(search_domain, order='date_from asc')
            
            if len(all_potential_allocs) > 1:
                # [DEDUPLICATION] If we have multiple, keep the "best" one and merge others.
                # "Best" is the one already marked as pro-rata or the one with leaves_taken.
                allocation = all_potential_allocs.filtered(lambda a: a.is_pro_rata_allocation)[:1] or all_potential_allocs[0]
                duplicates = all_potential_allocs - allocation
                _logger.warning(f"Found {len(duplicates)} duplicate allocations for {employee.name} in {service_year_start.year}. Merging...")
                for dup in duplicates:
                    if dup.leaves_taken > 0:
                        # This is tricky, but let's assume we can merge them if they are both pro-rata
                        _logger.error(f"Duplicate allocation {dup.id} has leaves taken! Manual intervention may be needed.")
                    dup.action_refuse()
                    dup.unlink()
            else:
                allocation = all_potential_allocs

            if not allocation:
                allocation_name = f"Annual Leave {service_year_start.year} for {employee.name}"
                expiry_date = service_year_start + relativedelta(years=2)
                allocation = self.env['hr.leave.allocation'].create({
                    'name': allocation_name, 'employee_id': employee.id,
                    'holiday_status_id': annual_leave_type.id, 'date_from': service_year_start,
                    'date_to': expiry_date, 'number_of_days': 0.01, # Create with a tiny positive value to pass validation
                    'is_pro_rata_allocation': True,
                    'notes': f"Accrual for service year.",
                })
                if allocation.state == 'draft': allocation.action_confirm()
                if allocation.state == 'confirm': allocation.action_validate()

            # 3. [REPAIR STEP] Correct Expiry Dates for existing records
            # If the allocation's date_from is pinned to the launch date, change it to service_year_start.
            # This automatically corrects the expiry_date calculation in hr.leave.allocation.
            if allocation.date_from != service_year_start:
                _logger.info(f"Repairing date_from for {employee.name} (Allocation ID: {allocation.id}). Changing {allocation.date_from} to {service_year_start}")
                allocation.write({
                    'date_from': service_year_start,
                    'date_to': service_year_start + relativedelta(years=2),
                    'is_pro_rata_allocation': True
                })

            # 3. Calculate the total TARGET balance as of today
            base_entitlement = {'non_management': 16, 'manager': 17, 'director': 20, 'chief': 24}.get(employee.leave_entitlement_class, 16)
            additional_days = max(0, years_of_service)
            total_annual_entitlement = min(base_entitlement + additional_days, 30)
            daily_rate = total_annual_entitlement / 365.25
            
            days_into_service_year = (today - accrual_start_point).days + 1
            target_balance = days_into_service_year * daily_rate

            # 4. Set the allocation's value directly to the correct target
            allocation.write({
                'number_of_days': target_balance, 
                'name': f"Annual Leave {service_year_start.year} for {employee.name}",
                'is_pro_rata_allocation': True
            })
            _logger.info(f"Set allocation for {employee.name} (Year {service_year_start.year}) to {target_balance:.4f} days.")

            # 5. [NEW] Finalize Previous Pro-Rata Allocations if they are still "open"
            # If we've moved to a new service year, any previous pro-rata allocations should be capped at their final year-end value.
            prev_allocations = self.env['hr.leave.allocation'].search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id', '=', annual_leave_type.id),
                ('is_pro_rata_allocation', '=', True),
                ('date_from', '<', service_year_start),
                ('state', '=', 'validate'),
            ])
            for prev_alloc in prev_allocations:
                # Calculate what the final balance SHOULD be for that year
                p_service_year_start = prev_alloc.date_from
                p_service_year_end = p_service_year_start + relativedelta(years=1) - timedelta(days=1)
                
                # Accrual period for that year: from max(launch, year_start) to year_end
                p_accrual_start = max(accrual_launch_date, p_service_year_start) if accrual_launch_date else p_service_year_start
                if p_service_year_end >= p_accrual_start:
                    p_days = (p_service_year_end - p_accrual_start).days + 1
                    # Entitlement logic for that specific year (DOJ-based)
                    p_years = p_service_year_start.year - doj.year
                    p_entitlement = min(base_entitlement + max(0, p_years), 30)
                    p_final_balance = p_days * (p_entitlement / 365.25)
                    
                    if abs(prev_alloc.number_of_days - p_final_balance) > 0.0001:
                        prev_alloc.write({'number_of_days': p_final_balance})
                        _logger.info(f"Finalized PREVIOUS year allocation ({p_service_year_start.year}) for {employee.name} at {p_final_balance:.4f} days.")

        _logger.info("Simple, state-based daily accrual process finished.")
    
    #

    def _action_create_paternity_allocation(self):
        """
        This action checks if an employee is male and, if so, creates a
        3-day paternity leave allocation if one doesn't already exist.
        This is designed to be triggered automatically.
        """
        _logger.info(f"Checking paternity allocation for {len(self)} employee(s)...")
        paternity_leave_type = self.env.ref('ahadu_hr_leave.ahadu_leave_type_paternity', raise_if_not_found=False)
        if not paternity_leave_type:
            _logger.warning("Paternity Leave type not found. Cannot create allocation.")
            return

        # We only care about male employees - using sudo() to ensure visibility of gender info
        male_employees = self.sudo().filtered(lambda emp: emp.gender_updated == 'male')
        if not male_employees:
            return

        for employee in male_employees:
            # --- ROBUST DUPLICATE CHECK ---
            # Check if a paternity allocation already exists for this employee.
            domain = [
                ('employee_id', '=', employee.id),
                ('holiday_status_id', '=', paternity_leave_type.id),
                ('state', '=', 'validate'), # Check only for already approved allocations
            ]
            if self.env['hr.leave.allocation'].search_count(domain) > 0:
                _logger.info(f"Skipping {employee.name}: Paternity allocation already exists.")
                continue

            # If no allocation exists, create one.
            _logger.info(f"Creating 3-day paternity allocation for {employee.name}.")
            
            # Paternity leave typically doesn't expire, but we can set a very long duration for safety.
            # A better approach might be to not set an expiry date. Let's assume it doesn't expire.
            allocation_name = f"Paternity Leave Entitlement for {employee.name}"
            
            new_allocation = self.env['hr.leave.allocation'].create({
                'name': allocation_name,
                'employee_id': employee.id,
                'holiday_status_id': paternity_leave_type.id,
                'number_of_days': 3,
                'notes': "Automatic 3-day paternity leave allocation.",
            })
            # Validate the allocation to make the days available immediately
            if new_allocation.state == 'draft': new_allocation.action_confirm()
            if new_allocation.state == 'confirm': new_allocation.action_validate()

    def _action_create_maternity_allocation(self):
        """
        Creates the initial 120-day maternity leave allocation for female
        employees if one doesn't already exist.
        """
        _logger.info(f"Checking initial maternity leave allocation for {len(self)} employee(s)...")
        maternity_leave_type = self.env.ref('ahadu_hr_leave.ahadu_leave_type_maternity', raise_if_not_found=False)
        if not maternity_leave_type:
            return

        for employee in self.sudo().filtered(lambda e: e.gender_updated == 'female'):
            domain = [('employee_id', '=', employee.id), ('holiday_status_id', '=', maternity_leave_type.id)]
            if self.env['hr.leave.allocation'].search_count(domain) == 0:
                _logger.info(f"Creating 120-day Maternity Leave allocation for {employee.name}.")
                new_alloc = self.env['hr.leave.allocation'].create({
                    'name': f"Maternity Leave Entitlement for {employee.name}",
                    'employee_id': employee.id,
                    'holiday_status_id': maternity_leave_type.id,
                    'number_of_days': 120,
                    'notes': "Automatic 120-day maternity leave allocation for female employees.",
                })
                if new_alloc.state == 'draft': new_alloc.action_confirm()
                if new_alloc.state == 'confirm': new_alloc.action_validate()

    def _action_create_event_based_allocations(self):
        """
        This single action handles the creation of fixed-amount, event-based
        allocations like Marriage and Bereavement leave.
        It is designed to be triggered on employee creation or update.
        """
        _logger.info(f"Checking event-based allocations for {len(self)} employee(s)...")
        
        # Get references to our leave types
        marriage_leave_type = self.env.ref('ahadu_hr_leave.ahadu_leave_type_marriage', raise_if_not_found=False)
        bereavement_leave_type = self.env.ref('ahadu_hr_leave.ahadu_leave_type_bereavement', raise_if_not_found=False)

        for employee in self:
            # --- 1. Handle Marriage Leave Allocation ---
            if marriage_leave_type:
                # Condition: Employee must be single
                if employee.marital == 'single':
                    # Check if a marriage allocation already exists
                    domain = [('employee_id', '=', employee.id), ('holiday_status_id', '=', marriage_leave_type.id)]
                    if self.env['hr.leave.allocation'].search_count(domain) == 0:
                        _logger.info(f"Creating 3-day Marriage Leave allocation for single employee {employee.name}.")
                        new_alloc = self.env['hr.leave.allocation'].create({
                            'name': f"Marriage Leave Entitlement for {employee.name}",
                            'employee_id': employee.id,
                            'holiday_status_id': marriage_leave_type.id,
                            'number_of_days': 3,
                            'notes': "Automatic 3-day marriage leave allocation for single employees.",
                        })
                        if new_alloc.state == 'draft': new_alloc.action_confirm()
                        if new_alloc.state == 'confirm': new_alloc.action_validate()

            # --- 2. Handle Bereavement Leave Allocation ---
            if bereavement_leave_type:
                # Condition: All employees are eligible
                # Check if a bereavement allocation already exists
                domain = [('employee_id', '=', employee.id), ('holiday_status_id', '=', bereavement_leave_type.id)]
                if self.env['hr.leave.allocation'].search_count(domain) == 0:
                    _logger.info(f"Creating 3-day Bereavement Leave allocation for {employee.name}.")
                    new_alloc = self.env['hr.leave.allocation'].create({
                        'name': f"Bereavement Leave Entitlement for {employee.name}",
                        'employee_id': employee.id,
                        'holiday_status_id': bereavement_leave_type.id,
                        'number_of_days': 3,
                        'notes': "Automatic 3-day bereavement leave allocation.",
                    })
                    if new_alloc.state == 'draft': new_alloc.action_confirm()
                    if new_alloc.state == 'confirm': new_alloc.action_validate()

    def _action_create_sick_leave_allocation(self):
        """
        Creates the initial 180-day sick leave allocation for employees if it doesn't exist.
        """
        _logger.info(f"Checking initial sick leave allocation for {len(self)} employee(s)...")
        sick_leave_type = self.env.ref('ahadu_hr_leave.ahadu_sick_leave_request', raise_if_not_found=False)
        if not sick_leave_type:
            return

        for employee in self:
            domain = [('employee_id', '=', employee.id), ('holiday_status_id', '=', sick_leave_type.id)]
            if self.env['hr.leave.allocation'].search_count(domain) == 0:
                _logger.info(f"Creating 180-day Sick Leave allocation for {employee.name}.")
                new_alloc = self.env['hr.leave.allocation'].create({
                    'name': f"Sick Leave Entitlement for {employee.name}",
                    'employee_id': employee.id,
                    'holiday_status_id': sick_leave_type.id,
                    'number_of_days': 180,
                    'notes': "Automatic 180-day sick leave allocation.",
                })
                if new_alloc.state == 'draft': new_alloc.action_confirm()
                if new_alloc.state == 'confirm': new_alloc.action_validate()

    def _reset_maternity_allocation(self):
        """
        This method is called by a one-time cron job to reset a single
        employee's maternity leave balance back to 120 days.
        """
        self.ensure_one()
        _logger.info(f"Executing scheduled reset of Maternity Leave for {self.name}.")
        maternity_leave_type = self.env.ref('ahadu_hr_leave.ahadu_leave_type_maternity', raise_if_not_found=False)
        if not maternity_leave_type:
            return
            
        allocation = self.env['hr.leave.allocation'].search([
            ('employee_id', '=', self.id),
            ('holiday_status_id', '=', maternity_leave_type.id),
        ], limit=1)
        
        if allocation:
            # Simply set the balance back to the full 120 days.
            allocation.write({'number_of_days': 120})
            _logger.info(f"Maternity Leave for {self.name} has been reset to 120 days.")

    def _reset_paternity_bereavement_allocation(self, leave_type_xml_id):
        """
        Resets the balance of a specific 3-day allocation type for the employee.
        Called by a scheduled one-time cron.
        """
        self.ensure_one()
        _logger.info(f"Executing scheduled replenishment of {leave_type_xml_id} for {self.name}.")
        leave_type = self.env.ref(leave_type_xml_id, raise_if_not_found=False)
        if not leave_type:
            return
            
        allocation = self.env['hr.leave.allocation'].search([
            ('employee_id', '=', self.id),
            ('holiday_status_id', '=', leave_type.id),
        ], limit=1)
        
        if allocation:
            allocation.write({'number_of_days': 3})
            _logger.info(f"Leave type {leave_type.name} for {self.name} has been replenished to 3 days.")

    @api.model_create_multi
    def create(self, vals_list):
        """ Override create to automatically grant paternity leave. """
        # First, create the employee records
        employees = super(HrEmployee, self).create(vals_list)
        
        # Check if automatic allocation is enabled in settings
        auto_allocate = self.env['ir.config_parameter'].sudo().get_param(
            'ahadu_hr_leave.auto_allocate_leaves', default='True'
        )
        
        # Then, run our allocation logic on the newly created employees (if enabled)
        if auto_allocate == 'True':
            employees._action_create_paternity_allocation()
            employees._action_create_event_based_allocations()
            employees._action_create_sick_leave_allocation()
            employees._action_create_maternity_allocation()
        return employees

    def write(self, vals):
        """ Override write to handle gender changes and cleanup allocations. """
        # Capture current gender to see if it changes
        res = super(HrEmployee, self).write(vals)

        if 'gender_updated' in vals or 'marital' in vals:
            if 'gender_updated' in vals:
                # Get references to the leave types
                paternity_type = self.env.ref('ahadu_hr_leave.ahadu_leave_type_paternity', raise_if_not_found=False)
                maternity_type = self.env.ref('ahadu_hr_leave.ahadu_leave_type_maternity', raise_if_not_found=False)
                
                for employee in self:
                    # If gender changed to FEMALE, remove any Paternity allocations
                    if employee.gender_updated == 'female' and paternity_type:
                        p_allocs = self.env['hr.leave.allocation'].sudo().search([
                            ('employee_id', '=', employee.id),
                            ('holiday_status_id', '=', paternity_type.id)
                        ])
                        for alloc in p_allocs:
                            if alloc.leaves_taken <= 0:
                                # Standard Odoo prevents deleting validated (Approved) records.
                                # Refuse it first, then we can delete it.
                                alloc.action_refuse()
                                alloc.unlink()
                                _logger.info(f"Removed Paternity allocation for {employee.name} following gender correction to Female.")

                    # If gender changed to MALE, remove any Maternity allocations
                    elif employee.gender_updated == 'male' and maternity_type:
                        m_allocs = self.env['hr.leave.allocation'].sudo().search([
                            ('employee_id', '=', employee.id),
                            ('holiday_status_id', '=', maternity_type.id)
                        ])
                        for alloc in m_allocs:
                            if alloc.leaves_taken <= 0:
                                # Standard Odoo prevents deleting validated (Approved) records.
                                # Refuse it first, then we can delete it.
                                alloc.action_refuse()
                                alloc.unlink()
                                _logger.info(f"Removed Maternity allocation for {employee.name} following gender correction to Male.")

            # Check if automatic allocation is enabled in settings
            auto_allocate = self.env['ir.config_parameter'].sudo().get_param(
                'ahadu_hr_leave.auto_allocate_leaves', default='True'
            )
            
            # Trigger creation of correct allocations (if enabled)
            if auto_allocate == 'True':
                self.sudo()._action_create_paternity_allocation()
                self.sudo()._action_create_event_based_allocations()
                self.sudo()._action_create_maternity_allocation()

        return res

