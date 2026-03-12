# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

class EthiopianDateConverter:
    """
    A self-contained utility to convert dates between the Gregorian and Ethiopian calendars.
    This implementation has no external dependencies.
    """
    # Ethiopian month names in Amharic (and English transliteration)
    MONTH_NAMES = [
        "", "መስከረም (Meskerem)", "ጥቅምት (Tekemt)", "ኅዳር (Hidar)", "ታኅሣሥ (Tahsas)",
        "ጥር (Tir)", "የካቲት (Yekatit)", "መጋቢት (Megabit)", "ሚያዝያ (Miyazya)",
        "ግንቦት (Ginbot)", "ሰኔ (Sene)", "ሐምሌ (Hamle)", "ነሐሴ (Nehase)", "ጳጉሜን (Pagumē)"
    ]

    def is_gregorian_leap(self, year):
        return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)

    def to_ethiopian(self, year, month, day):
        """Converts a Gregorian date (year, month, day) to an Ethiopian date tuple."""
        if self.is_gregorian_leap(year):
            # In a Gregorian leap year, the Ethiopian new year is on September 12
            new_year_day = 254
        else:
            # Otherwise, it's on September 11
            new_year_day = 253
            
        # Get the day of the year for the Gregorian date
        gregorian_day_of_year = datetime(year, month, day).timetuple().tm_yday

        et_year = 0
        if gregorian_day_of_year > new_year_day:
            # We are after the Ethiopian new year
            days_into_et_year = gregorian_day_of_year - new_year_day
            et_year = year - 7
        else:
            # We are before the Ethiopian new year
            # We need to check the previous Gregorian year's leap status for the offset
            if self.is_gregorian_leap(year - 1):
                days_into_et_year = gregorian_day_of_year + 111
            else:
                days_into_et_year = gregorian_day_of_year + 110
            et_year = year - 8

        # Calculate Ethiopian month and day
        et_month = (days_into_et_year - 1) // 30 + 1
        et_day = (days_into_et_year - 1) % 30 + 1

        return (et_year, et_month, et_day)

    def to_gregorian(self, et_year, et_month, et_day):
        """Converts an Ethiopian date to a Gregorian datetime.date object."""
        # The Ethiopian new year in the Gregorian calendar is usually Sept 11
        gregorian_year = et_year + 7
        
        # Check if the next Gregorian year is a leap year to determine the start date
        if self.is_gregorian_leap(gregorian_year + 1):
            new_year_start = datetime(gregorian_year, 9, 12)
        else:
            new_year_start = datetime(gregorian_year, 9, 11)
            
        # Calculate the number of days to add from the start of the Ethiopian year
        days_to_add = (et_month - 1) * 30 + (et_day - 1)
        
        gregorian_date = new_year_start + timedelta(days=days_to_add)
        return gregorian_date.date()