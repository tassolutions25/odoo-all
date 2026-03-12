from odoo.tests.common import TransactionCase
from datetime import date

class TestAhaduOvertime(TransactionCase):

    def setUp(self):
        super(TestAhaduOvertime, self).setUp()
        self.Employee = self.env['hr.employee']
        self.Overtime = self.env['ahadu.overtime']
        self.Contract = self.env['hr.contract']
        
        # Create Employee
        self.employee = self.Employee.create({'name': 'Test Employee'})
        
        # Create Contract
        self.contract = self.Contract.create({
            'name': 'Test Contract',
            'employee_id': self.employee.id,
            'wage': 13625.00, # From User Screenshot example (Salary 13,625)
            'state': 'open',
            'date_start': date(2025, 1, 1),
        })

    def test_overtime_calculation(self):
        """ Test calculation based on user scenario (Nov 18, 2025 - Dec 17, 2025) """
        
        # Create Overtime Request
        overtime = self.Overtime.create({
            'employee_id': self.employee.id,
            'date_from': date(2025, 11, 18),
            'date_to': date(2025, 12, 17),
        })
        
        # Trigger computations (if not auto-triggered, but create usually does)
        # We might need to ensure resource.calendar.leaves is empty for this period or matches expectation.
        # User said "0 Holiday". So we ensure no global leaves overlap.
        # In a real test db, there might be demo data.
        
        # Verify Days
        self.assertEqual(overtime.total_calendar_days, 30, "Total days should be 30")
        
        # Specific Dates Check:
        # Nov 18 (Tue) to Dec 17 (Wed)
        # Saturdays: 
        # Nov 22, Nov 29, Dec 6, Dec 13 -> 4 Saturdays
        # Sundays:
        # Nov 23, Nov 30, Dec 7, Dec 14 -> 4 Sundays
        
        self.assertEqual(overtime.saturdays, 4, "Should be 4 Saturdays")
        self.assertEqual(overtime.sundays, 4, "Should be 4 Sundays")
        
        # Verify Hours
        # Gross: 30 * 8 = 240
        self.assertEqual(overtime.gross_possible_hours, 240, "Gross hours should be 240")
        
        # Off Hours: 
        # Sat: 4 * 4 = 16
        # Sun: 4 * 8 = 32
        # Hol: 0
        # Total Off: 48
        self.assertEqual(overtime.off_hours_saturday, 16)
        self.assertEqual(overtime.off_hours_sunday, 32)
        self.assertEqual(overtime.total_off_hours, 48)
        
        # Working Hours
        # 240 - 48 = 192
        self.assertEqual(overtime.total_working_hours, 192, "Working hours should be 192")
        
        # Hourly Rate
        # 13625 / 192 = 70.9635... -> 70.96
        self.assertAlmostEqual(overtime.hourly_rate, 70.9635, places=2)
        
        # Add Lines
        # Normal 1.5 hrs -> Rate 1.5
        line1 = self.env['ahadu.overtime.line'].create({
            'overtime_id': overtime.id,
            'date': date(2025, 11, 20),
            'type': 'normal',
            'hours': 1.5
        })
        
        # Night 1.75 hrs -> Rate 1.75 (Wait, user screenshot said "Night 1.75" is the RATE or Hours?
        # Screenshot: "Night 1.75" row, "Duration" = 1.75. Rate = 1.75.
        # So 1.75 hours * 1.75 Rate.
        line2 = self.env['ahadu.overtime.line'].create({
            'overtime_id': overtime.id,
            'date': date(2025, 11, 20),
            'type': 'night',
            'hours': 1.75
        })
        
        # Calculate Amounts (approx)
        # Rate/Hr = 70.9635...
        # Line 1: 1.5 * 1.5 * 70.9635 = 2.25 * 70.9635 = 159.667
        # Line 2: 1.75 * 1.75 * 70.9635 = 3.0625 * 70.9635 = 217.325
        
        # Total: 159.667 + 217.325 = 376.99
        
        # User screenshot total for 51.25 hours is 5481.93.
        # My lines are just samples.
        
        self.assertTrue(line1.amount > 0)
