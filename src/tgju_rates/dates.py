"""Dates for display: Gregorian (2026-10-04) or, with --jalali, the Persian solar calendar (1405/07/12)."""

from datetime import datetime

# Days before each Gregorian month in a common year.
DAYS_BEFORE_MONTH = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)


def to_jalali(year, month, day):
    """The Jalali (year, month, day) of a Gregorian date.

    Counts days from a fixed epoch, then splits them into 33-year cycles (12053 days) and 4-year
    groups (1461 days). Jalali months 1-6 have 31 days and 7-11 have 30.
    """
    leap_year = year + 1 if month > 2 else year
    days = (
        355666
        + 365 * year
        + (leap_year + 3) // 4
        - (leap_year + 99) // 100
        + (leap_year + 399) // 400
        + day
        + DAYS_BEFORE_MONTH[month - 1]
    )
    jalali_year = -1595 + 33 * (days // 12053)
    days %= 12053
    jalali_year += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jalali_year += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        return jalali_year, 1 + days // 31, 1 + days % 31
    return jalali_year, 7 + (days - 186) // 30, 1 + (days - 186) % 30


def format_date(day, jalali=False):
    """A date as 2026-10-04, or 1405/07/12 with ``jalali``; takes a date or datetime."""
    if not jalali:
        return f"{day:%Y-%m-%d}"
    year, month, date = to_jalali(day.year, day.month, day.day)
    return f"{year}/{month:02}/{date:02}"


def format_stamp(stamp, jalali=False, seconds=False):
    """A Unix time as local date and time, e.g. "2026-10-04 16:03" or "1405/07/12 16:03:46"."""
    moment = datetime.fromtimestamp(stamp)
    clock = f"{moment:%H:%M:%S}" if seconds else f"{moment:%H:%M}"
    return f"{format_date(moment, jalali)} {clock}"
