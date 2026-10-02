import os
import tempfile
import unittest
from pathlib import Path

from tgju_rates.history import History
from tgju_rates.holdings import (
    Holding,
    TotalTrend,
    load_holdings,
    merge_holdings,
    parse_holding,
    total_worth,
    value_holdings,
)


def rate(key, price, change="(0%) 0"):
    return {"key": key, "name": "", "price": price, "change": change, "low": "1", "high": "2", "time": ""}


class ParseHoldingTest(unittest.TestCase):
    def test_amount_only(self):
        self.assertEqual(parse_holding("usd=1,200"), Holding("price_dollar_rl", 1200))

    def test_fractional_amount_and_cost_in_rial(self):
        self.assertEqual(parse_holding(" EUR = 0.5 @ 2,900,000 "), Holding("price_eur", 0.5, 2900000))

    def test_cost_follows_toman_flag_unless_unit_given(self):
        self.assertEqual(parse_holding("eur=1@290,000", toman=True).cost, 2900000)
        self.assertEqual(parse_holding("eur=1@2,900,000 rial", toman=True).cost, 2900000)
        self.assertEqual(parse_holding("eur=1@290,000 Toman").cost, 2900000)

    def test_rejects_bad_syntax(self):
        for text in ("usd", "usd=abc", "usd=1@", "usd=1@5 dollars"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_holding(text)


class LoadHoldingsTest(unittest.TestCase):
    def write(self, text):
        handle, path = tempfile.mkstemp(suffix=".txt")
        os.close(handle)
        self.addCleanup(os.remove, path)
        Path(path).write_text(text, encoding="utf-8")
        return path

    def test_missing_file_is_no_holdings(self):
        self.assertEqual(load_holdings("/nonexistent/holdings.txt"), [])

    def test_comments_blank_lines_and_rial_prices(self):
        path = self.write("# savings\n\nusd=100@2,000,000  # bought in spring\neur=5\n")
        self.assertEqual(load_holdings(path), [Holding("price_dollar_rl", 100, 2000000), Holding("price_eur", 5)])

    def test_bad_line_is_named(self):
        path = self.write("usd=1\noops\n")
        with self.assertRaisesRegex(ValueError, "line 2"):
            load_holdings(path)

    def test_option_replaces_file_line(self):
        merged = merge_holdings([Holding("price_eur", 1), Holding("price_gbp", 2)], [Holding("price_eur", 9)])
        self.assertEqual(merged, [Holding("price_eur", 9), Holding("price_gbp", 2)])


class ValueHoldingsTest(unittest.TestCase):
    RATES = [rate("price_eur", "3,000,000", "(1%) 30,000"), rate("price_gbp", "4,000,000", "(-2%) -80,000")]

    def test_worth_gain_and_today(self):
        valuation = value_holdings([Holding("price_eur", 2, 2000000), Holding("price_gbp", 1)], self.RATES)
        eur, gbp = valuation.positions
        self.assertEqual((eur.worth, eur.today, eur.today_percent), (6000000, 60000, 1.0))
        self.assertAlmostEqual(eur.gain_percent, 50.0)
        self.assertIsNone(gbp.gain_percent)
        self.assertEqual(valuation.worth, 10000000)
        self.assertAlmostEqual(valuation.gain_percent, 50.0)  # only holdings with a cost count
        self.assertEqual(valuation.today, -20000)
        self.assertAlmostEqual(valuation.today_percent, -20000 / 10020000 * 100)

    def test_unknown_price_is_left_out_and_total_marked_incomplete(self):
        valuation = value_holdings([Holding("price_eur", 1), Holding("price_xau", 1)], self.RATES)
        self.assertIsNone(valuation.positions[1].worth)
        self.assertEqual(valuation.worth, 3000000)
        self.assertIsNone(valuation.complete_worth)


class TotalTrendTest(unittest.TestCase):
    HOLDINGS = [Holding("price_eur", 2), Holding("price_gbp", 1)]

    def test_total_needs_every_price(self):
        self.assertIsNone(total_worth(self.HOLDINGS, {"price_eur": 5}))
        self.assertEqual(total_worth(self.HOLDINGS, {"price_eur": 5, "price_gbp": 7}), 17)

    def test_adds_only_changes(self):
        trend = TotalTrend(3)
        for total in (1, 1, None, 2, 3, 4):
            trend.add(total)
        self.assertEqual(list(trend.values), [2, 3, 4])

    def test_seed_replays_history_in_time_order(self):
        history = History.open(":memory:")
        self.addCleanup(history.close)
        history.record([rate("price_eur", "10")], 100)
        history.record([rate("price_gbp", "1")], 101)
        history.record([rate("price_eur", "20")], 102)
        trend = TotalTrend(10)
        trend.seed(history, self.HOLDINGS, now=200)
        self.assertEqual(list(trend.values), [21, 41])


if __name__ == "__main__":
    unittest.main()
