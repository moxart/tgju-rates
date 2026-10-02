import unittest

from tgju_rates.ansi import DOWN, FLAT, UP
from tgju_rates.table import change_style, render_table, sparkline, trend_style
from tgju_rates.tracking import HIGHLIGHT_SECONDS, PriceTracker


def rate(key, price, change="(0%) 0"):
    return {"key": key, "name": "نام", "price": price, "change": change, "low": "1", "high": "2", "time": ""}


class SparklineTest(unittest.TestCase):
    def test_needs_two_points(self):
        self.assertEqual(sparkline([]), "")
        self.assertEqual(sparkline([5]), "")

    def test_scales_between_own_low_and_high(self):
        self.assertEqual(sparkline([10, 20, 15]), "▁█▅")

    def test_flat_prices(self):
        self.assertEqual(sparkline([7, 7, 7]), "▁▁▁")

    def test_trend_style(self):
        self.assertEqual(trend_style([1, 2]), UP)
        self.assertEqual(trend_style([2, 1]), DOWN)
        self.assertEqual(trend_style([2, 3, 2]), FLAT)


class ChangeStyleTest(unittest.TestCase):
    def test_colours_by_sign_of_percentage(self):
        self.assertEqual(change_style("(0.5%) 100"), UP)
        self.assertEqual(change_style("(-0.5%) -100"), DOWN)
        self.assertEqual(change_style("(0%) 0"), FLAT)
        self.assertEqual(change_style("-"), FLAT)


class RenderTableTest(unittest.TestCase):
    def test_plain_table_without_tracker(self):
        lines = render_table([rate("price_eur", "2,923,500")], color=False).split("\n")

        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("   CODE"))
        self.assertNotIn("TREND", lines[0])
        self.assertIn("Euro", lines[2])
        self.assertIn("292,350", lines[2])  # toman
        self.assertNotIn("\033", "".join(lines))

    def test_live_table_marks_recent_moves_and_adds_trend(self):
        rates = [rate("price_eur", "100")]
        tracker = PriceTracker()
        tracker.update(rates, now=0)
        rates[0]["price"] = "110"
        tracker.update(rates, now=1)

        fresh = render_table(rates, color=False, tracker=tracker, now=2).split("\n")
        stale = render_table(rates, color=False, tracker=tracker, now=1 + HIGHLIGHT_SECONDS).split("\n")

        self.assertIn("TREND", fresh[0])
        self.assertTrue(fresh[2].startswith(" ▲ "))
        self.assertIn("▁█", fresh[2])
        self.assertTrue(stale[2].startswith("   "))

    def test_persian_column_is_last(self):
        header = render_table([rate("price_eur", "1")], color=False, persian=True).split("\n")[0]
        self.assertTrue(header.endswith("PERSIAN"))

    def test_columns_line_up(self):
        lines = render_table([rate("price_eur", "1"), rate("price_gbp", "3,000,000")], color=False).split("\n")
        self.assertEqual(lines[2].index("Euro"), lines[3].index("British Pound"))


if __name__ == "__main__":
    unittest.main()
