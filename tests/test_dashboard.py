import re
import unittest
from unittest import mock

from tgju_rates.app import LiveSession, Options
from tgju_rates.dashboard import arrange, group_by_market, percent_text, render_dashboard
from tgju_rates.tracking import PriceTracker

ANSI = re.compile(r"\033\[[\d;?]*[A-Za-z]")


def rate(key, price, change="(0.5%) 100"):
    return {"key": key, "name": "", "price": price, "change": change, "low": "1", "high": "2", "time": ""}


RATES = [
    rate("price_dollar_rl", "2,672,200"),
    rate("sekee", "2,716,550,000", "(-1.25%) -100"),
    rate("price_eur", "3,017,500"),
    rate("crypto-bitcoin-irr", "228,975,876,000"),
]


class DashboardTest(unittest.TestCase):
    def test_groups_by_market_in_first_seen_order(self):
        groups = group_by_market(RATES)
        self.assertEqual([market for market, _ in groups], ["currency", "coin", "crypto"])
        self.assertEqual([r["key"] for r in groups[0][1]], ["price_dollar_rl", "price_eur"])

    def test_percent_text(self):
        self.assertEqual(percent_text("(0.5%) 100"), "+0.50%")
        self.assertEqual(percent_text("(-1.25%) -100"), "-1.25%")
        self.assertEqual(percent_text("-"), "-")

    def test_panels_sit_side_by_side_when_wide_and_stack_when_narrow(self):
        wide = render_dashboard(RATES, color=False, width=200).split("\n")
        self.assertIn("CURRENCIES", wide[0])
        self.assertIn("GOLD COINS", wide[0])
        self.assertIn("CRYPTO", wide[0])
        narrow = render_dashboard(RATES, color=False, width=40)
        self.assertEqual([line.split()[0] for line in narrow.split("\n\n")], ["CURRENCIES", "GOLD", "CRYPTO"])

    def test_four_panels_go_two_by_two_with_aligned_columns(self):
        panels = [(["a"], 30), (["b"], 20), (["c"], 25), (["d"], 30)]
        rows, columns = arrange(panels, 100)
        self.assertEqual([len(row) for row in rows], [2, 2])
        self.assertEqual(columns, [30, 30])

    def test_toman_and_plain_rows(self):
        lines = render_dashboard(RATES[:1], color=False, toman=True).split("\n")
        self.assertEqual(lines[1].split(), ["CODE", "PRICE", "(TOMAN)", "CHANGE"])
        self.assertEqual(lines[2].split(), ["USD", "267,220", "+0.50%"])

    def test_coloured_rows_keep_their_width_while_animating(self):
        tracker = PriceTracker()
        tracker.update(RATES, now=0)
        moved = [dict(RATES[0], price="2,700,000"), *RATES[1:]]
        tracker.update(moved, now=10)
        for animation in ("flash", "roll", "off"):
            with self.subTest(animation=animation):
                view = dict(tracker=tracker, now=10.2, width=200)
                coloured = render_dashboard(moved, color=True, animation=animation, **view).split("\n")
                plain = render_dashboard(moved, color=False, **view).split("\n")
                visible = [ANSI.sub("", line).rstrip() for line in coloured[:3]]
                self.assertEqual([len(line) for line in visible], [len(line) for line in plain[:3]])
                self.assertIn("▲", plain[2])


@mock.patch("tgju_rates.app.terminal_width", return_value=200)
@mock.patch("tgju_rates.app.fetch_live_prices", return_value={"current": {}})
class LiveDashboardTest(unittest.TestCase):
    def test_live_frame_shows_panels_with_trends(self, _fetch, _width):
        session = LiveSession(RATES, RATES, [], 10, Options(dashboard=True), color=False)
        session.poll()
        frame = session.frame(0)
        self.assertIn("GOLD COINS", frame)
        self.assertIn("TREND", frame)
        self.assertNotIn("HIGH", frame)


if __name__ == "__main__":
    unittest.main()
