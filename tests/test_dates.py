import unittest
from datetime import date, datetime

from tgju_rates.dates import format_date, format_stamp, to_jalali


class ToJalaliTest(unittest.TestCase):
    def test_known_dates(self):
        cases = {
            (2024, 3, 20): (1403, 1, 1),  # Nowruz 1403
            (2025, 3, 20): (1403, 12, 30),  # 1403 is a leap year
            (2025, 3, 21): (1404, 1, 1),
            (2024, 3, 19): (1402, 12, 29),
            (2026, 10, 4): (1405, 7, 12),
            (2026, 9, 22): (1405, 6, 31),  # the last 31-day month ends
            (2026, 9, 23): (1405, 7, 1),
            (2000, 1, 1): (1378, 10, 11),
        }
        for gregorian, jalali in cases.items():
            with self.subTest(gregorian=gregorian):
                self.assertEqual(to_jalali(*gregorian), jalali)


class FormatTest(unittest.TestCase):
    def test_format_date(self):
        self.assertEqual(format_date(date(2026, 10, 4)), "2026-10-04")
        self.assertEqual(format_date(date(2026, 10, 4), jalali=True), "1405/07/12")

    def test_format_stamp_is_local_time(self):
        stamp = datetime(2026, 10, 4, 9, 5, 7).timestamp()
        self.assertEqual(format_stamp(stamp), "2026-10-04 09:05")
        self.assertEqual(format_stamp(stamp, jalali=True, seconds=True), "1405/07/12 09:05:07")


if __name__ == "__main__":
    unittest.main()
