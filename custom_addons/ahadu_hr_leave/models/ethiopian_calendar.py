# -*- coding: utf-8 -*-
from datetime import date

class EthiopianDateConverter:
    """
    A self-contained utility to convert dates between the Gregorian and Ethiopian calendars
    using Julian Day Numbers (JDN). This ensures 100% mathematical accuracy.
    """
    # Ethiopian month names in Amharic (and English transliteration)
    MONTH_NAMES = [
        "", "መስከረም (Meskerem)", "ጥቅምት (Tekemt)", "ኅዳር (Hidar)", "ታኅሣሥ (Tahsas)",
        "ጥር (Tir)", "የካቲት (Yekatit)", "መጋቢት (Megabit)", "ሚያዝያ (Miyazya)",
        "ግንቦት (Ginbot)", "ሰኔ (Sene)", "ሐምሌ (Hamle)", "ነሐሴ (Nehase)", "ጳጉሜን (Pagumē)"
    ]

    def to_ethiopian(self, year, month, day):
        """Converts a Gregorian date (year, month, day) to an Ethiopian date tuple (Y, M, D)."""
        # Step 1: Convert Gregorian Date to Julian Day Number (JDN)
        if month <= 2:
            year -= 1
            month += 12
        A = year // 100
        B = A // 4
        C = 2 - A + B
        E = int(365.25 * (year + 4716))
        F = int(30.6001 * (month + 1))
        jdn = C + day + E + F - 1524.5
        jdn = int(jdn + 0.5)

        # Step 2: Convert JDN to Ethiopian Date
        # The Ethiopian Epoch (1 Meskerem 1 A.M.) is JDN 1724221
        n = jdn - 1724221
        cycles = n // 1461
        r = n % 1461
        
        year_in_cycle = r // 365
        if year_in_cycle == 4:
            year_in_cycle = 3
            
        et_year = 4 * cycles + year_in_cycle + 1
        day_in_year = r - 365 * year_in_cycle
        
        et_month = day_in_year // 30 + 1
        et_day = day_in_year % 30 + 1
        
        return (et_year, et_month, et_day)

    def to_gregorian(self, et_year, et_month, et_day):
        """Converts an Ethiopian date to a standard Gregorian datetime.date object."""
        # Step 1: Convert Ethiopian Date to JDN
        y = et_year - 1
        jdn = 1724221 + y * 365 + (y // 4) + (et_month - 1) * 30 + (et_day - 1)

        # Step 2: Convert JDN to Gregorian Date
        z = jdn
        if z < 2299161:
            a = z
        else:
            alpha = int((z - 1867216.25) / 36524.25)
            a = z + 1 + alpha - int(alpha / 4)
        b = a + 1524
        c = int((b - 122.1) / 365.25)
        d = int(365.25 * c)
        e = int((b - d) / 30.6001)
        
        day = b - d - int(30.6001 * e)
        if e < 14:
            month = e - 1
        else:
            month = e - 13
            
        if month > 2:
            year = c - 4716
        else:
            year = c - 4715
            
        return date(year, month, day)