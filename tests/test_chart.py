import unittest
from datetime import datetime

from tgju_rates.chart import daily_rows, daily_summary, render_chart, resample


def at(text):
    return datetime.strptime(text, "%Y-%m-%d %H:%M").timestamp()


class ResampleTest(unittest.TestCase):
    def test_prices_hold_until_the_next_change(self):
        points = [(10, 100), (35, 200)]
        self.assertEqual(resample(points, 0, 40, 4), [100, 100, 100, 200])
        self.assertEqual(resample([(25, 5)], 0, 40, 4), [None, None, 5, 5])


class RenderChartTest(unittest.TestCase):
    def test_shape_and_labels(self):
        lines = render_chart([100, None, 150, 200], 0, 3600, height=4).splitlines()
        self.assertEqual(len(lines), 6)  # 4 rows, the axis, the time labels
        self.assertTrue(lines[0].startswith("200 ┤"))
        self.assertTrue(lines[3].startswith("100 ┤"))
        self.assertEqual(lines[0][-1], "█")  # the high fills the top row
        self.assertEqual(lines[3][5:], "▁ ██")  # the low is one step; no data is blank
        self.assertEqual(lines[4], "    └────")

    def test_flat_line_sits_mid_height(self):
        lines = render_chart([7, 7], 0, 60, height=4).splitlines()
        self.assertEqual(lines[0], "7 ┤")
        self.assertTrue(lines[3].endswith("██"))


class DailySummaryTest(unittest.TestCase):
    def test_open_low_high_close_per_day(self):
        points = [(at("2026-10-01 09:00"), 100), (at("2026-10-01 15:00"), 90), (at("2026-10-02 10:00"), 120)]
        rows = daily_rows(points)
        self.assertEqual([row[1:] for row in rows], [(100, 90, 100, 90), (120, 120, 120, 120)])
        lines = daily_summary(points).splitlines()
        self.assertEqual(lines[0].split(), ["DATE", "OPEN", "LOW", "HIGH", "CLOSE", "CHANGE"])
        self.assertTrue(lines[2].endswith("+30 (+33.3%)"))

    def test_summary_in_jalali_and_limited_to_the_last_days(self):
        points = [(at("2026-10-03 09:00"), 100), (at("2026-10-04 10:00"), 120)]
        lines = daily_summary(points, jalali=True, last=1).splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[1].startswith("1405/07/12"))
        self.assertTrue(lines[1].endswith("+20 (+20.0%)"))  # still measured from the hidden day


if __name__ == "__main__":
    unittest.main()
