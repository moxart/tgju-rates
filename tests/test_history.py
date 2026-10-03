import unittest

from tgju_rates.app import format_chart, format_history
from tgju_rates.history import History
from tgju_rates.tracking import PriceTracker


def rates_at(**prices):
    return [{"key": f"price_{code}", "price": f"{price:,}"} for code, price in prices.items()]


class HistoryTest(unittest.TestCase):
    def setUp(self):
        self.history = History.open(":memory:")
        self.addCleanup(self.history.close)

    def test_saves_only_changed_prices(self):
        self.history.record(rates_at(eur=100, gbp=200), now=1)
        self.history.record(rates_at(eur=100, gbp=210), now=2)
        self.history.record([{"key": "price_eur", "price": "-"}], now=3)

        self.assertEqual(self.history.changes_since("price_eur", 0), [(1, 100)])
        self.assertEqual(self.history.changes_since("price_gbp", 0), [(1, 200), (2, 210)])
        self.assertEqual(self.history.changes_since("price_gbp", 2), [(2, 210)])

    def test_latest_and_last_before(self):
        self.history.record(rates_at(eur=100, gbp=200), now=1)
        self.history.record(rates_at(eur=110, gbp=200), now=5)

        self.assertEqual(self.history.latest(), {"price_eur": (5, 110), "price_gbp": (1, 200)})
        self.assertEqual(self.history.last_before("price_eur", 5), (1, 100))
        self.assertIsNone(self.history.last_before("price_eur", 1))

    def test_reopening_continues_from_last_saved_price(self):
        self.history.record(rates_at(eur=100), now=1)
        self.history.record(rates_at(eur=110), now=2)

        reopened = History(self.history._db)
        reopened.record(rates_at(eur=110), now=3)
        self.assertEqual(len(reopened.changes_since("price_eur", 0)), 2)

    def test_recent_prices_are_oldest_first(self):
        for now, price in enumerate([1, 2, 3, 4]):
            self.history.record(rates_at(eur=price), now=now)
        self.assertEqual(self.history.recent_prices("price_eur", 3), [2, 3, 4])

    def test_saved_trend_seeds_tracker_without_duplicating_current_price(self):
        tracker = PriceTracker()
        tracker.load_trends({"price_eur": [90, 100], "price_gbp": []})
        tracker.update(rates_at(eur=100, gbp=5), now=0)

        self.assertEqual(list(tracker.trends["price_eur"]), [90, 100])
        self.assertEqual(list(tracker.trends["price_gbp"]), [5])
        self.assertIsNone(tracker.recent_move("price_eur", 0))


class FormatHistoryTest(unittest.TestCase):
    def test_lists_changes_with_moves_and_summary(self):
        text = format_history("price_eur", 1, [(0, 1000), (60, 1500), (120, 1200)])
        lines = text.split("\n")

        self.assertIn("EUR (Euro)", lines[0])
        self.assertIn("in rial", lines[0])
        self.assertTrue(lines[3].endswith("1,500  ▲ 500"))
        self.assertTrue(lines[4].endswith("1,200  ▼ 300"))
        self.assertIn("low 1,000   high 1,500", lines[-1])

    def test_toman(self):
        text = format_history("price_eur", 1, [(0, 1000), (60, 1500)], toman=True)
        self.assertIn("in toman", text)
        self.assertIn("150  ▲ 50", text)

    def test_empty(self):
        self.assertIn("No saved prices", format_history("price_eur", 2, []))

    def test_chart(self):
        text = format_chart("price_eur", 1, [(0, 1000), (3600, 1500)], 0, 7200, toman=True, width=40)
        lines = text.split("\n")
        self.assertIn("in toman", lines[0])
        self.assertTrue(lines[2].startswith("150 ┤"))
        self.assertIn("DATE", text)
        self.assertIn("No saved prices", format_chart("price_eur", 1, [], 0, 1))


if __name__ == "__main__":
    unittest.main()
