# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase
from datetime import datetime, timedelta, date
import logging

_logger = logging.getLogger(__name__)


class TestAttendanceLOP(TransactionCase):
    """Test attendance-based Loss of Pay calculation."""
    
    def setUp(self):
        super().setUp()
        
        # Create test employee
        self.employee = self.env['hr.employee'].create({
            'name': 'Test Employee LOP',
            'emp_wage': 26000.0,  # 26,000 ETB per month
        })
        
        # Create cost center
        self.cost_center = self.env['ahadu.cost.center'].create({
            'name': 'Test Branch LOP',
            'code': 'TEST_LOP',
        })
        
        # Create contract
        self.contract = self.env['hr.contract'].create({
            'name': 'Test Contract LOP',
            'employee_id': self.employee.id,
            'emp_wage': 26000.0,
            'cost_center_id': self.cost_center.id,
            'state': 'open',
            'date_start': '2024-01-01',
        })
        
        # Get salary structure
        self.structure = self.env.ref('ahadu_payroll.structure_ahadu_monthly', raise_if_not_found=False)
    
    def test_working_days_calculation(self):
        """Test that working days excludes weekends."""
        
        if not self.structure:
            self.skipTest("Salary structure not found")
        
        # Create payslip for January 2024 (full month)
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'date_from': date(2024, 1, 1),
            'date_to': date(2024, 1, 31),
            'contract_id': self.contract.id,
            'struct_id': self.structure.id,
        })
        
        working_days = payslip._get_working_days()
        
        # January 2024 has 31 days total
        # Weekends: 6,7,13,14,20,21,27,28 = 8 days
        # Working days should be 31 - 8 = 23 days
        self.assertEqual(len(working_days), 23,
            f"January 2024 should have 23 working days, got {len(working_days)}")
        
        # Verify no weekends in working days
        for day in working_days:
            self.assertNotIn(day.weekday(), [5, 6],
                f"Working days should not include weekends, found {day}")
        
        _logger.info(f"✓ Working days calculation test passed: {len(working_days)} days")
    
    def test_full_attendance_no_deduction(self):
        """Test that full attendance results in zero deduction."""
        
        if not self.structure:
            self.skipTest("Salary structure not found")
        
        # Create payslip for January 2024
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'date_from': date(2024, 1, 1),
            'date_to': date(2024, 1, 31),
            'contract_id': self.contract.id,
            'struct_id': self.structure.id,
        })
        
        # Create attendance for ALL working days
        working_days = payslip._get_working_days()
        for day in working_days:
            self.env['hr.attendance'].create({
                'employee_id': self.employee.id,
                'check_in': datetime.combine(day, datetime.min.time().replace(hour=9)),
                'check_out': datetime.combine(day, datetime.min.time().replace(hour=17)),
            })
        
        # Calculate deduction
        deduction = payslip._get_ahadu_leave_deduction()
        
        # Should be zero (no absences)
        self.assertEqual(deduction, 0.0,
            "Full attendance should result in zero deduction")
        
        _logger.info("✓ Full attendance test passed: deduction = 0.0")
    
    def test_unauthorized_absence_full_deduction(self):
        """Test that absence without leave results in full day deduction."""
        
        if not self.structure:
            self.skipTest("Salary structure not found")
        
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'date_from': date(2024, 1, 1),
            'date_to': date(2024, 1, 31),
            'contract_id': self.contract.id,
            'struct_id': self.structure.id,
        })
        
        working_days = payslip._get_working_days()
        num_working_days = len(working_days)
        daily_rate = 26000.0 / num_working_days
        
        # Employee is absent for 3 days (no attendance, no leave)
        # Mark first 3 working days as absent
        absent_days = working_days[:3]
        
        # Attend all days EXCEPT first 3
        for day in working_days[3:]:
            self.env['hr.attendance'].create({
                'employee_id': self.employee.id,
                'check_in': datetime.combine(day, datetime.min.time().replace(hour=9)),
                'check_out': datetime.combine(day, datetime.min.time().replace(hour=17)),
            })
        
        deduction = payslip._get_ahadu_leave_deduction()
        
        # Should deduct 3 full days
        expected = daily_rate * 3
        self.assertAlmostEqual(deduction, expected, places=2,
            msg=f"3 unauthorized absences should deduct {expected:.2f}, got {deduction:.2f}")
        
        _logger.info(f"✓ Unauthorized absence test passed: {len(absent_days)} days deducted = {deduction:.2f}")
    
    def test_approved_unpaid_leave_deduction(self):
        """Test that approved unpaid leave is correctly deducted."""
        
        if not self.structure:
            self.skipTest("Salary structure not found")
        
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'date_from': date(2024, 1, 1),
            'date_to': date(2024, 1, 31),
            'contract_id': self.contract.id,
            'struct_id': self.structure.id,
        })
        
        # Create unpaid leave type
        leave_type = self.env['hr.leave.type'].create({
            'name': 'Unpaid Leave Test',
            'unpaid': True,
            'requires_allocation': 'no',
        })
        
        # Create unpaid leave for 2 days (Jan 10-11, 2024)
        # Note: Jan 10 is Wednesday, Jan 11 is Thursday (both working days)
        self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'holiday_status_id': leave_type.id,
            'date_from': datetime(2024, 1, 10, 0, 0, 0),
            'date_to': datetime(2024, 1, 11, 23, 59, 59),
            'number_of_days': 2,
            'state': 'validate',
        })
        
        # Create attendance for all days EXCEPT leave days
        working_days = payslip._get_working_days()
        for day in working_days:
            if day not in [date(2024, 1, 10), date(2024, 1, 11)]:
                self.env['hr.attendance'].create({
                    'employee_id': self.employee.id,
                    'check_in': datetime.combine(day, datetime.min.time().replace(hour=9)),
                    'check_out': datetime.combine(day, datetime.min.time().replace(hour=17)),
                })
        
        deduction = payslip._get_ahadu_leave_deduction()
        
        # Should deduct 2 days for unpaid leave
        daily_rate = 26000.0 / len(working_days)
        expected = daily_rate * 2
        
        self.assertAlmostEqual(deduction, expected, places=2,
            msg=f"2 days unpaid leave should deduct {expected:.2f}, got {deduction:.2f}")
        
        _logger.info(f"✓ Unpaid leave test passed: 2 days deducted = {deduction:.2f}")
    
    def test_approved_paid_leave_no_deduction(self):
        """Test that approved paid leave (annual leave) has no deduction."""
        
        if not self.structure:
            self.skipTest("Salary structure not found")
        
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'date_from': date(2024, 1, 1),
            'date_to': date(2024, 1, 31),
            'contract_id': self.contract.id,
            'struct_id': self.structure.id,
        })
        
        # Create paid leave type (annual leave)
        leave_type = self.env['hr.leave.type'].create({
            'name': 'Annual Leave Test',
            'unpaid': False,  # Paid leave
            'requires_allocation': 'no',
        })
        
        # Create paid leave for 3 days
        self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'holiday_status_id': leave_type.id,
            'date_from': datetime(2024, 1, 15, 0, 0, 0),
            'date_to': datetime(2024, 1, 17, 23, 59, 59),
            'number_of_days': 3,
            'state': 'validate',
        })
        
        # Create attendance for all days EXCEPT leave days
        working_days = payslip._get_working_days()
        for day in working_days:
            if day not in [date(2024, 1, 15), date(2024, 1, 16), date(2024, 1, 17)]:
                self.env['hr.attendance'].create({
                    'employee_id': self.employee.id,
                    'check_in': datetime.combine(day, datetime.min.time().replace(hour=9)),
                    'check_out': datetime.combine(day, datetime.min.time().replace(hour=17)),
                })
        
        deduction = payslip._get_ahadu_leave_deduction()
        
        # Should be zero (paid leave, no deduction)
        self.assertEqual(deduction, 0.0,
            "Paid leave (annual leave) should have zero deduction")
        
        _logger.info("✓ Paid leave test passed: deduction = 0.0")
    
    def test_mixed_scenario(self):
        """Test complex scenario with attendance, paid leave, unpaid leave, and absence."""
        
        if not self.structure:
            self.skipTest("Salary structure not found")
        
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'date_from': date(2024, 1, 1),
            'date_to': date(2024, 1, 31),
            'contract_id': self.contract.id,
            'struct_id': self.structure.id,
        })
        
        # Create leave types
        paid_leave = self.env['hr.leave.type'].create({
            'name': 'Paid Leave',
            'unpaid': False,
            'requires_allocation': 'no',
        })
        
        unpaid_leave = self.env['hr.leave.type'].create({
            'name': 'Unpaid Leave',
            'unpaid': True,
            'requires_allocation': 'no',
        })
        
        # Scenario:
        # - Jan 8-9: Paid leave (no deduction)
        # - Jan 10-11: Unpaid leave (full deduction)
        # - Jan 15: Unauthorized absence (full deduction)
        # - Rest: Full attendance
        
        self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'holiday_status_id': paid_leave.id,
            'date_from': datetime(2024, 1, 8, 0, 0, 0),
            'date_to': datetime(2024, 1, 9, 23, 59, 59),
            'number_of_days': 2,
            'state': 'validate',
        })
        
        self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'holiday_status_id': unpaid_leave.id,
            'date_from': datetime(2024, 1, 10, 0, 0, 0),
            'date_to': datetime(2024, 1, 11, 23, 59, 59),
            'number_of_days': 2,
            'state': 'validate',
        })
        
        # Create attendance for all days except leaves and Jan 15
        working_days = payslip._get_working_days()
        for day in working_days:
            if day not in [date(2024, 1, 8), date(2024, 1, 9),  # Paid leave
                          date(2024, 1, 10), date(2024, 1, 11),  # Unpaid leave
                          date(2024, 1, 15)]:  # Unauthorized absence
                self.env['hr.attendance'].create({
                    'employee_id': self.employee.id,
                    'check_in': datetime.combine(day, datetime.min.time().replace(hour=9)),
                    'check_out': datetime.combine(day, datetime.min.time().replace(hour=17)),
                })
        
        deduction = payslip._get_ahadu_leave_deduction()
        
        # Expected deduction:
        # - Paid leave (2 days): 0
        # - Unpaid leave (2 days): 2 * daily_rate
        # - Unauthorized (1 day): 1 * daily_rate
        # Total: 3 * daily_rate
        
        daily_rate = 26000.0 / len(working_days)
        expected = daily_rate * 3
        
        self.assertAlmostEqual(deduction, expected, places=2,
            msg=f"Mixed scenario should deduct {expected:.2f}, got {deduction:.2f}")
        
        _logger.info(f"✓ Mixed scenario test passed: deduction = {deduction:.2f} (3 days)")
