import unittest
from unittest import mock

from tgju_rates.alerts import parse_alert
from tgju_rates.app import LiveSession, Options, history_csv, saved_rates
from tgju_rates.history import History
from tgju_rates.holdings import Holding


def rate(key, price):
    return {"key": key, "name": "", "price": price, "change": "(0%) 0", "low": "1", "high": "2", "time": ""}


class FakeKeys:
    """Hands out one batch of key presses per read, then quits (Enter first, in case a filter is being typed)."""

    def __init__(self, *batches):
        self.batches = [list(batch) for batch in batches] + [["\r", "q"]]
        self.waits = []

    def read(self, timeout):
        self.waits.append(timeout)
        return self.batches.pop(0)


@mock.patch("tgju_rates.app.fetch_live_prices", return_value={"current": {}})
class LiveSessionKeysTest(unittest.TestCase):
    def session(self):
        rates = [rate("price_eur", "2,900,000"), rate("price_gbp", "3,400,000")]
        return LiveSession(rates, rates, [], 10, Options(), color=False)

    def test_key_redraws_at_once_and_q_quits(self, _fetch):
        frames = []
        self.session().run(frames.append, FakeKeys("t"))
        self.assertEqual(len(frames), 2)  # the first poll, then the redraw after "t"
        self.assertIn("PRICE (RIAL)", frames[0])
        self.assertIn("PRICE (TOMAN)", frames[1])
        self.assertIn("Keys:", frames[0])

    def test_filter_hides_rows(self, _fetch):
        frames = []
        self.session().run(frames.append, FakeKeys("/gbp"))
        self.assertIn("GBP", frames[-1])
        self.assertNotIn("EUR", frames[-1])

    def test_no_match_says_so(self, _fetch):
        frames = []
        self.session().run(frames.append, FakeKeys("/zzz"))
        self.assertIn("No currency matches", frames[-1])

    def test_pause_waits_for_a_key_without_polling(self, _fetch):
        keys = FakeKeys("p", [])
        frames = []
        self.session().run(frames.append, keys)
        self.assertIsNone(keys.waits[1])
        self.assertIn("PAUSED", frames[-1])
        self.assertEqual(_fetch.call_count, 1)


@mock.patch("tgju_rates.app.fetch_live_prices")
class LiveSessionAnimationTest(unittest.TestCase):
    def run_session(self, fetch, animation):
        fetch.return_value = {"price_eur": {"p": "3,000,000", "l": "1", "h": "2", "t": "", "d": "100,000", "dp": "3.4"}}
        rates = [rate("price_eur", "2,900,000")]
        session = LiveSession(rates, rates, [], 10, Options(animation=animation), color=True)
        keys = FakeKeys(*[[]] * 100)
        frames = []
        # Each call moves the clock on 20ms, enough for the animation to finish well before the keys run out.
        clock = (step * 0.02 for step in range(100000))
        with mock.patch("tgju_rates.app.time.time", side_effect=lambda: next(clock)):
            session.run(frames.append, keys)
        return frames, keys

    def test_frames_play_until_the_animation_settles(self, fetch):
        frames, keys = self.run_session(fetch, "flash")
        self.assertIn("48;5;34", frames[0])
        self.assertNotIn("48;5;34", frames[-1])
        self.assertLessEqual(keys.waits[0], 1 / 15)
        self.assertGreater(keys.waits[-1], 1)  # settled: back to waiting for the next poll

    def test_off_waits_for_the_next_poll(self, fetch):
        frames, keys = self.run_session(fetch, "off")
        self.assertNotIn("48;5;34", frames[0])
        self.assertGreater(keys.waits[0], 1)


@mock.patch("tgju_rates.app.notify")
@mock.patch("tgju_rates.app.fetch_live_prices", return_value={"current": {}})
class LiveSessionHoldingsTest(unittest.TestCase):
    def test_savings_panel_follows_the_unit_key_and_total_alert_fires(self, _fetch, notify):
        rates = [rate("price_eur", "2,900,000")]
        session = LiveSession(
            rates, rates, [parse_alert("total>1")], 10, Options(), color=False, holdings=[Holding("price_eur", 2)]
        )
        frames = []
        session.run(frames.append, FakeKeys("t"))
        self.assertIn("WORTH (RIAL)", frames[0])
        self.assertIn("5,800,000", frames[0])
        self.assertIn("WORTH (TOMAN)", frames[1])
        self.assertIn("580,000", frames[1])
        notify.assert_called_once()
        self.assertIn("TOTAL", notify.call_args[0][0])


class LiveSessionBackoffTest(unittest.TestCase):
    def test_failures_double_the_wait_up_to_the_cap_and_success_resets_it(self):
        rates = [rate("price_eur", "2,900,000")]
        session = LiveSession(rates, rates, [], 10, Options(), color=False)
        with mock.patch("tgju_rates.app.fetch_live_prices", side_effect=OSError("down")):
            delays = []
            for _ in range(6):
                session.poll()
                delays.append(session.poll_delay())
        self.assertEqual(delays, [20, 40, 80, 120, 120, 120])
        self.assertIn("retrying in 120s: down", session.status)
        with mock.patch("tgju_rates.app.fetch_live_prices", return_value={}):
            session.poll()
        self.assertEqual(session.poll_delay(), 10)
        self.assertEqual(session.status, "connected")

    def test_long_interval_is_never_shortened(self):
        session = LiveSession([], [], [], 300, Options(), color=False)
        session.failures = 3
        self.assertEqual(session.poll_delay(), 300)

    def test_notice_is_shown_above_the_table(self):
        session = LiveSession([], [], [], 10, Options(), color=False, notice="list from history")
        self.assertIn("NOTE list from history", session.frame(0))


class SavedRatesTest(unittest.TestCase):
    def test_rebuilds_rows_for_the_failed_markets_in_name_order(self):
        history = History.open(":memory:")
        self.addCleanup(history.close)
        history.record([rate("price_gbp", "3,400,000"), rate("price_eur", "2,900,000"), rate("sekee", "9")], now=0)
        history.record([rate("price_eur", "3,000,000")], now=60)

        rows = saved_rates(history, ["currency"])
        self.assertEqual(
            [(row["key"], row["price"], row["change"]) for row in rows],
            [
                ("price_eur", "3,000,000", "-"),
                ("price_gbp", "3,400,000", "-"),
            ],
        )
        [coin] = saved_rates(history, ["coin"])
        self.assertEqual(coin["name"], "سکه امامی")


class HistoryCsvTest(unittest.TestCase):
    def test_csv(self):
        lines = history_csv("price_eur", [(0, 1005), (60, 1500)], toman=True).splitlines()
        self.assertEqual(lines[0], "time,code,price_toman")
        self.assertTrue(lines[1].endswith(",EUR,100"))
        self.assertEqual(len(lines), 3)


if __name__ == "__main__":
    unittest.main()
