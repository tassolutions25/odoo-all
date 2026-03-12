# -*- coding: utf-8 -*-
from odoo import models, api, fields
from . import ethiopian_calendar
import calendar
from datetime import date, timedelta

class AhaduCalendarView(models.AbstractModel):
    _name = 'ahadu.calendar.view'
    _description = 'Ahadu Calendar View Data'

    @api.model
    def get_calendar_data(self, year):
        """
        Prepares and returns all necessary data for BOTH Gregorian and Ethiopian
        calendar grids for a given year.
        """
        year = int(year)
        today = date.today()
        converter = ethiopian_calendar.EthiopianDateConverter()
        employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)

        # Fetch all relevant leaves for the employee for the given Gregorian year
        leaves = self.env['hr.leave'].search([
            ('employee_id', '=', employee.id),
            ('state', 'in', ['validate', 'confirm', 'refuse']),
            ('request_date_from', '>=', date(year, 1, 1)),
            ('request_date_from', '<=', date(year, 12, 31)),
        ])
        leave_dates = {leave.request_date_from: leave.state for leave in leaves}

        public_holidays = {}
        public_holidays_list = []
        # Find the public holidays linked to the employee's specific working hours calendar
        if employee.resource_calendar_id and employee.resource_calendar_id.public_holidays_id:
            # The dates are in the 'line_ids' of the public holiday calendar
            holiday_lines = employee.resource_calendar_id.public_holidays_id.line_ids.filtered(
                lambda l: l.date.year == year
            )
            public_holidays = {h.date: h.name for h in holiday_lines}
            public_holidays_list = [{'date': h.date.strftime('%B %d, %Y'), 'name': h.name} for h in holiday_lines]

        # --- PART 1: Generate Gregorian Calendar Data (Jan - Dec) ---
        gregorian_months = []
        for month_num in range(1, 13):
            month_name = calendar.month_name[month_num]
            month_weeks = []
            for week in calendar.monthcalendar(year, month_num):
                week_days = []
                for day_num in week:
                    if day_num == 0:
                        week_days.append({'is_day': False})
                    else:
                        gregorian_date = date(year, month_num, day_num)
                        week_days.append({
                            'is_day': True,
                            'gregorian_day': day_num,
                            'is_today': gregorian_date == today,
                            'is_leave': gregorian_date in leave_dates,
                            'leave_status': leave_dates.get(gregorian_date),
                            'is_holiday': gregorian_date in public_holidays,
                            'holiday_name': public_holidays.get(gregorian_date)
                        })
                month_weeks.append(week_days)
            gregorian_months.append({'name': month_name, 'weeks': month_weeks})

        # --- PART 2: Generate Ethiopian Calendar Data (Meskerem - Pagume) ---
        # Determine the Ethiopian year that starts in the selected Gregorian year
        et_year_start_greg = converter.to_gregorian(year - 8, 1, 1) # A rough start
        et_year = converter.to_ethiopian(et_year_start_greg.year, et_year_start_greg.month, et_year_start_greg.day)[0]
        if converter.to_gregorian(et_year, 1, 1).year < year:
            et_year += 1

        ethiopian_months = []
        for et_month_num in range(1, 14): # 13 Ethiopian months
            month_name = converter.MONTH_NAMES[et_month_num]
            
            # Determine days in month (Pagume can be 5 or 6)
            days_in_month = 30
            if et_month_num == 13:
                # Ethiopian leap year if the NEXT Gregorian year is a leap year
                next_greg_year = converter.to_gregorian(et_year, 13, 5).year
                days_in_month = 6 if calendar.isleap(next_greg_year) else 5

            month_weeks = []
            week_days = []
            
            # Get the weekday of the 1st day of the Ethiopian month (0=Monday, 6=Sunday)
            # We align it to our grid (0=Sunday)
            first_day_greg = converter.to_gregorian(et_year, et_month_num, 1)
            padding_days = (first_day_greg.weekday() + 1) % 7
            
            # Add empty padding cells for the first week
            for _ in range(padding_days):
                week_days.append({'is_day': False})

            for day_num in range(1, days_in_month + 1):
                gregorian_date = converter.to_gregorian(et_year, et_month_num, day_num)
                week_days.append({
                    'is_day': True,
                    'ethiopian_day': day_num,
                    'is_today': gregorian_date == today,
                    'is_leave': gregorian_date in leave_dates,
                    'leave_status': leave_dates.get(gregorian_date),
                    'is_holiday': gregorian_date in public_holidays,
                    'holiday_name': public_holidays.get(gregorian_date)
                })
                # If we've reached the end of a week, start a new row
                if (len(week_days) % 7 == 0):
                    month_weeks.append(week_days)
                    week_days = []
            
            # Add the last week if it's not full
            if week_days:
                month_weeks.append(week_days)

            ethiopian_months.append({'name': month_name, 'weeks': month_weeks})

        return {
            'year': year,
            'gregorian_months': gregorian_months,
            'ethiopian_months': ethiopian_months,
            'public_holidays': public_holidays_list,
            'legend_data': {
                'validated': 'Validated', 'confirm': 'To Approve',
                'refused': 'Refused', 'holiday': 'Public Holiday'
            }
        }