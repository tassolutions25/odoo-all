from odoo.tests.common import TransactionCase
from datetime import date, datetime

class TestOvertimeTracking(TransactionCase):

    def setUp(self):
        super(TestOvertimeTracking, self).setUp()
        self.tracking_model = self.env['ahadu.overtime.tracking']
        self.line_model = self.env['ahadu.overtime.tracking.line']
        
        self.employee = self.env['hr.employee'].create({'name': 'Test Employee'})
        self.tracking = self.tracking_model.create({
            'employee_id': self.employee.id,
            'date_from': '2025-01-01',
            'date_to': '2025-01-31',
        })

    def test_split_logic_normal_morning(self):
        """ Test Morning 06:00 - 08:00 is Normal (1.5) """
        # Monday Jan 6 2025
        # 06:00 AM to 08:00 AM
        line = self.line_model.create({
            'tracking_id': self.tracking.id,
            'date': '2025-01-06',
            'start_hour': '06', 'start_minute': '00', 'start_am_pm': 'am',
            'end_hour': '08', 'end_minute': '00', 'end_am_pm': 'am',
        })
        self.assertEqual(line.normal_hours, 2.0)
        self.assertEqual(line.night_hours, 0.0)

    def test_split_logic_regular_work(self):
        """ Test Day 08:00 - 05:00 PM is Regular (0 OT) """
        # Monday Jan 6 2025
        line = self.line_model.create({
            'tracking_id': self.tracking.id,
            'date': '2025-01-06',
            'start_hour': '08', 'start_minute': '00', 'start_am_pm': 'am',
            'end_hour': '05', 'end_minute': '00', 'end_am_pm': 'pm',
        })
        self.assertEqual(line.total_hours, 9.0)
        self.assertEqual(line.normal_hours, 0.0)
        self.assertEqual(line.night_hours, 0.0)

    def test_split_logic_normal_evening(self):
        """ Test Evening 05:00 PM - 10:00 PM is Normal (1.5) """
        # Monday Jan 6 2025
        line = self.line_model.create({
            'tracking_id': self.tracking.id,
            'date': '2025-01-06',
            'start_hour': '05', 'start_minute': '00', 'start_am_pm': 'pm',
            'end_hour': '10', 'end_minute': '00', 'end_am_pm': 'pm',
        })
        self.assertEqual(line.normal_hours, 5.0)
        self.assertEqual(line.night_hours, 0.0)

    def test_split_logic_night(self):
        """ Test Night 10:00 PM - 12:00 AM is Night (1.75) """
        # Monday Jan 6 2025
        line = self.line_model.create({
            'tracking_id': self.tracking.id,
            'date': '2025-01-06',
            'start_hour': '10', 'start_minute': '00', 'start_am_pm': 'pm',
            'end_hour': '12', 'end_minute': '00', 'end_am_pm': 'am', # 12 AM is midnight (next day?) Logic handles "End <= Start" as next day
        })
        # 10 PM = 22, 12 AM = 0 (24). 
        # Logic converts 12am -> 0h. 0 < 22, so treated as End+1day = 24.
        # Interval 22 to 24 = 2 hours.
        self.assertEqual(line.normal_hours, 0.0)
        self.assertEqual(line.night_hours, 2.0)

    def test_split_logic_mixed_evening_night(self):
        """ Test crossing 22:00 boundary: 06 PM to 11 PM """
        # Monday Jan 6 2025: 18:00 to 23:00 (5h)
        # 18-22 (4h) Normal
        # 22-23 (1h) Night
        
        # 6 PM
        # 11 PM
        line = self.line_model.create({
            'tracking_id': self.tracking.id,
            'date': '2025-01-06',
            'start_hour': '06', 'start_minute': '00', 'start_am_pm': 'pm',
            'end_hour': '11', 'end_minute': '00', 'end_am_pm': 'pm',
        })
        self.assertEqual(line.normal_hours, 4.0)
        self.assertEqual(line.night_hours, 1.0)

    def test_saturday_weekend_window(self):
        """ Test Sat 01:00 PM - 05:00 PM is Weekend """
        # Saturday Jan 4 2025
        line = self.line_model.create({
            'tracking_id': self.tracking.id,
            'date': '2025-01-04',
            'start_hour': '01', 'start_minute': '00', 'start_am_pm': 'pm',
            'end_hour': '05', 'end_minute': '00', 'end_am_pm': 'pm',
        })
        self.assertEqual(line.weekend_hours, 4.0)
        self.assertEqual(line.normal_hours, 0.0)

    def test_sunday_all_day_weekend(self):
        """ Test Sunday is all Weekend """
        # Sunday Jan 5 2025
        # 08 AM - 08 PM
        line = self.line_model.create({
            'tracking_id': self.tracking.id,
            'date': '2025-01-05',
            'start_hour': '08', 'start_minute': '00', 'start_am_pm': 'am',
            'end_hour': '08', 'end_minute': '00', 'end_am_pm': 'pm',
        })
        # 08 to 20 = 12h
        self.assertEqual(line.weekend_hours, 12.0)
        self.assertEqual(line.normal_hours, 0.0)
        self.assertEqual(line.night_hours, 0.0)
