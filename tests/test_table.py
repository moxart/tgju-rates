import unittest

from tgju_rates.ansi import DEFAULT_BACKGROUND, DOWN, FLAT, STRIPE, UP
from tgju_rates.holdings import Holding, value_holdings
from tgju_rates.table import change_style, render_holdings, render_table, sparkline, trend_style
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

    def test_toman_leads_and_converts_change_low_high(self):
        row = rate("price_eur", "2,923,500", change="(-0.5%) -14,500")
        row["low"], row["high"] = "2,885,300", "2,926,400"
        header, _, line = render_table([row], color=False, toman=True).split("\n")

        self.assertLess(header.index("PRICE (TOMAN)"), header.index("RIAL"))
        self.assertEqual(
            line.split(),
            ["EUR", "Euro", "292,350", "2,923,500", "(-0.5%)", "-1,450", "288,530", "292,640"],
        )

    def test_persian_column_is_last(self):
        header = render_table([rate("price_eur", "1")], color=False, persian=True).split("\n")[0]
        self.assertTrue(header.endswith("PERSIAN"))

    def test_columns_line_up(self):
        lines = render_table([rate("price_eur", "1"), rate("price_gbp", "3,000,000")], color=False).split("\n")
        self.assertEqual(lines[2].index("Euro"), lines[3].index("British Pound"))


class AnimationTest(unittest.TestCase):
    def moved(self):
        rates = [rate("price_eur", "1,000"), rate("price_gbp", "2,000,000")]
        tracker = PriceTracker()
        tracker.update(rates, now=0)
        rates[0]["price"], rates[1]["price"] = "900", "2,000,500"
        tracker.update(rates, now=10)
        return rates, tracker

    def test_flash_sets_a_background_and_hands_it_back_to_the_row(self):
        rates, tracker = self.moved()
        lines = render_table(rates, color=True, tracker=tracker, now=10, animation="flash").split("\n")
        self.assertIn("48;5;160", lines[2])  # EUR fell
        self.assertIn(DEFAULT_BACKGROUND, lines[2])
        self.assertIn("48;5;34", lines[3])  # GBP rose, on a striped row
        self.assertIn(STRIPE, lines[3].split("48;5;34", 1)[1])

    def test_roll_spins_digits_without_changing_widths(self):
        rates, tracker = self.moved()
        spinning = render_table(rates, color=True, tracker=tracker, now=10, animation="roll")
        settled = render_table(rates, color=True, tracker=tracker, now=20, animation="roll")
        self.assertNotIn("2,000,500", spinning)
        self.assertIn("2,000,500", settled)
        self.assertEqual(len(spinning), len(settled))

    def test_off_and_plain_output_do_not_animate(self):
        rates, tracker = self.moved()
        still = render_table(rates, color=True, tracker=tracker, now=20, animation="flash")
        self.assertEqual(render_table(rates, color=True, tracker=tracker, now=10, animation="off"), still)
        plain = render_table(rates, color=False, tracker=tracker, now=10, animation="board")
        self.assertIn("2,000,500", plain)
        self.assertNotIn("\033", plain)


class RenderHoldingsTest(unittest.TestCase):
    def valuation(self):
        rates = [rate("price_eur", "3,000,000", "(1%) 30,000"), rate("price_gbp", "4,000,000", "(-2%) -80,000")]
        return value_holdings([Holding("price_eur", 2, 2000000), Holding("price_gbp", 0.25)], rates)

    def test_rows_and_total(self):
        lines = render_holdings(self.valuation(), color=False).split("\n")
        self.assertEqual(lines[0].split(), ["YOUR", "SAVINGS", "AMOUNT", "WORTH", "(RIAL)", "SINCE", "BOUGHT", "TODAY"])
        self.assertEqual(lines[1].split(), ["EUR", "2", "6,000,000", "▲", "+50.0%", "▲", "+1.0%"])
        self.assertEqual(lines[2].split(), ["GBP", "0.25", "1,000,000", "▼", "-2.0%"])
        self.assertEqual(lines[3].split()[:2], ["TOTAL", "7,000,000"])
        self.assertEqual(lines[1].index("6,000,000"), lines[3].index("7,000,000"))

    def test_toman_and_trend(self):
        text = render_holdings(self.valuation(), color=False, toman=True, trend=[1, 3, 2])
        self.assertIn("WORTH (TOMAN)", text)
        self.assertIn("700,000", text)
        self.assertTrue(text.endswith("▁█▅"))


if __name__ == "__main__":
    unittest.main()
