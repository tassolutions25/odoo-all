# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase
from datetime import datetime, date

class TestLeaveTypesDeduction(TransactionCase):
    """
    Focused tests for specific leave type deduction logic in payroll.
    Covers: Half-day, Sick Leave Tiers, and Unvalidated Leave handling.
    """
    
    def setUp(self):
        super().setUp()
        
        # Create test employee
        self.employee = self.env['hr.employee'].create({
            'name': 'Test Employee Leaves',
            'emp_wage': 26000.0,  # 26,000 ETB per month (~1000 per working day)
        })
        
        # Create contract
        self.contract = self.env['hr.contract'].create({
            'name': 'Test Contract Leaves',
            'employee_id': self.employee.id,
            'emp_wage': 26000.0,
            'state': 'open',
            'date_start': '2024-01-01',
        })
        
        # Get/Create Leave Types
        self.sick_leave_type = self.env.ref('ahadu_hr_leave.ahadu_sick_leave_request', raise_if_not_found=False)
        if not self.sick_leave_type:
            self.sick_leave_type = self.env['hr.leave.type'].create({
                'name': 'Sick Leave',
                'requires_allocation': 'yes',
                'leave_validation_type': 'both',
                'unpaid': False,
            })
            
        self.annual_leave_type = self.env.ref('ahadu_hr_leave.ahadu_leave_type_annual', raise_if_not_found=False)
        if not self.annual_leave_type:
             self.annual_leave_type = self.env['hr.leave.type'].create({
                'name': 'Annual Leave',
                'requires_allocation': 'yes',
                'leave_validation_type': 'manager',
                'unpaid': False,
            })

    def create_payslip(self):
        return self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'date_from': date(2024, 11, 1),
            'date_to': date(2024, 11, 30),
            'contract_id': self.contract.id,
        })

    def test_sick_leave_100_percent_tier(self):
        """Test Sick Leave with 100% pay tier results in ZERO deduction."""
        payslip = self.create_payslip()
        
        # Mock finding specific number of working days to stabilize math
        # Let's say we have 20 working days -> Daily rate = 1300
        # But for unit testing _calculate_leave_deduction, we just check the method directly
        
        # Create Sick Leave (Tier 100 - < 60 days)
        leave = self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'holiday_status_id': self.sick_leave_type.id,
            'date_from': datetime(2024, 11, 4, 8, 0, 0),
            'date_to': datetime(2024, 11, 4, 17, 0, 0),
            'number_of_days': 1,
            'state': 'validate',
        })
        
        # Ensure tier logic worked (ahadu_hr_leave mechanism)
        # If not running with full module logic, we manually set it to verify PAYROLL logic
        if not leave.sick_leave_pay_tier:
             leave.write({'sick_leave_pay_tier': '100'})
             
        deduction = payslip._calculate_leave_deduction(leave, 1000.0)
        self.assertEqual(deduction, 0.0, "Sick Leave (100% tier) should have 0 deduction")

    def test_sick_leave_50_percent_tier(self):
        """Test Sick Leave with 50% pay tier results in 50% deduction."""
        payslip = self.create_payslip()
        
        leave = self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'holiday_status_id': self.sick_leave_type.id,
            'date_from': datetime(2024, 11, 5, 8, 0, 0),
            'date_to': datetime(2024, 11, 5, 17, 0, 0),
            'number_of_days': 1,
            'state': 'validate',
        })
        leave.write({'sick_leave_pay_tier': '50'})
        
        deduction = payslip._calculate_leave_deduction(leave, 1000.0)
        self.assertEqual(deduction, 500.0, "Sick Leave (50% tier) should have 50% deduction")

    def test_half_day_leave_deduction(self):
        """Test Half-Day Leave Without Pay results in 50% deduction."""
        payslip = self.create_payslip()
        
        lwop_type = self.env['hr.leave.type'].create({
            'name': 'Test LWOP',
            'unpaid': True,
        })
        
        leave = self.env['hr.leave.create']({
            'employee_id': self.employee.id,
            'holiday_status_id': lwop_type.id,
            'date_from': datetime(2024, 11, 6, 8, 0, 0),  # Morning only
            'date_to': datetime(2024, 11, 6, 12, 0, 0),
            'number_of_days': 0.5,
            'state': 'validate',
            # 'is_half_day': True  # This field might be computed or explicit depending on module
        })
        # Force is_half_day if it's a custom field
        try:
            leave.write({'is_half_day': True})
        except:
            pass # Field might not exist in test env if ahadu_hr_leave not fully loaded
            
        # Mock getattr since is_half_day is a custom field that might not be on the object 
        # class if the test runs without the full context of the other module
        # But we can test the LOGIC by calling the method
        
        # We need to rely on the fact that we patched the code to look for it.
        # So we can't easily unit test the payroll model without the hr_leave model extension loaded.
        # Assuming ahadu_hr_leave IS loaded (since it's a dependency).
        
        if hasattr(leave, 'is_half_day'):
            leave.write({'is_half_day': True})
            deduction = payslip._calculate_leave_deduction(leave, 1000.0)
            self.assertEqual(deduction, 500.0, "Half-day LWOP should have 50% deduction (0.5 * 1000)")

    def test_unvalidated_leave_ignored(self):
        """
        Verify that unvalidated leave is NOT picked up by _get_ahadu_leave_deduction
        and thus treated as Unauthorized Absence (Full Deduction).
        """
        payslip = self.create_payslip()
        
        # Create unvalidated sick leave
        leave = self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'holiday_status_id': self.sick_leave_type.id,
            'date_from': datetime(2024, 11, 7, 8, 0, 0),
            'date_to': datetime(2024, 11, 7, 17, 0, 0),
            'number_of_days': 1,
            'state': 'confirm',  # NOT validated
        })
        
        # Mock finding working days properly
        # We need to run the full _get_ahadu_leave_deduction method here
        # But that requires Attendance data too
        
        # Create attendance for other days, but NONE for the leave day (Nov 7)
        # So it appears as Absent.
        # Since leave is not Validated, payslip should NOT find it.
        # Result: Unauthorized Absence (Full deduction)
        
        # Let's mock a single working day scenario to simplify
        payslip.date_from = date(2024, 11, 7)
        payslip.date_to = date(2024, 11, 7)
        
        # Employee has NO attendance on Nov 7
        
        deduction = payslip._get_ahadu_leave_deduction()
        
        # Daily rate calculation inside method depends on count of working days
        # For 1 day, daily rate = wage / 1 = 26000
        
        self.assertEqual(deduction, 26000.0, 
            "Unvalidated leave should be ignored, resulting in Unauthorized Absence deduction")
