import unittest
from unittest import mock

from tgju_rates.alerts import parse_alert
from tgju_rates.app import LiveSession, Options, history_csv, run_live, saved_rates
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
    def test_first_poll_does_not_flag_a_move(self, fetch):
        fetch.return_value = {"price_eur": {"p": "3,000,000", "l": "1", "h": "2", "t": "", "d": "0", "dp": "0"}}
        session = self.session()
        session.poll()
        self.assertIsNone(session.tracker.recent_move("price_eur", session.updated_at))

    def session(self):
        rates = [rate("price_eur", "2,900,000"), rate("price_gbp", "3,400,000")]
        return LiveSession(rates, rates, [], 10, Options(), color=False)

    def test_key_redraws_at_once_and_q_quits(self, _fetch):
        frames = []
        session = self.session()
        session.run(frames.append, FakeKeys("t"))
        self.assertEqual(len(frames), 2)  # the first poll, then the redraw after "t"
        self.assertIn("PRICE (RIAL)", frames[0])
        self.assertIn("PRICE (TOMAN)", frames[1])
        self.assertIn("● LIVE", frames[0])
        self.assertIn("t toman/rial", session.key_bar(200))

    def test_key_bar_drops_hints_that_do_not_fit_but_keeps_help_and_quit(self, _fetch):
        session = self.session()
        session.interactive = True
        bar = session.key_bar(40)
        self.assertIn("? help", bar)
        self.assertIn("q quit", bar)
        self.assertNotIn("p pause", bar)
        self.assertLessEqual(len(bar), 40)

    def test_key_bar_without_keys_only_says_how_to_quit(self, _fetch):
        self.assertEqual(self.session().key_bar(80), "Ctrl+C quit")

    def test_question_mark_opens_help_and_esc_closes_it(self, _fetch):
        frames = []
        session = self.session()
        session.run(frames.append, FakeKeys("?", "\x1b"))
        self.assertIn("KEYS", frames[1])
        self.assertNotIn("PRICE (RIAL)", frames[1])
        self.assertIn("PRICE (RIAL)", frames[2])

    def test_failed_poll_shows_offline_and_the_error(self, fetch):
        fetch.side_effect = OSError("down")
        frames = []
        self.session().run(frames.append, FakeKeys())
        self.assertIn("● OFFLINE", frames[0])
        self.assertIn("⚠ feed error, retrying in 20s: down", frames[0])

    def test_filter_hides_rows(self, _fetch):
        frames = []
        self.session().run(frames.append, FakeKeys("/gbp"))
        self.assertIn("GBP", frames[-1])
        self.assertNotIn("EUR", frames[-1])

    def test_c_shows_a_conversion_from_polled_prices(self, _fetch):
        frames = []
        self.session().run(frames.append, FakeKeys(["c", *"2 eur gbp"], ["\r"]))
        self.assertIn("convert: 2 eur gbp_  →  2 EUR = 1.71 GBP", frames[-2])
        self.assertIn("convert: 2 eur gbp  →  2 EUR = 1.71 GBP   (c to edit, Esc to close)", frames[-1])
        self.assertEqual(_fetch.call_count, 1)  # no fetch of its own

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
        session.tracker.update(rates, -1)  # an earlier poll at the old price
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


class RunLivePipedTest(unittest.TestCase):
    def test_piped_output_keeps_colour_but_does_not_animate(self):
        sessions = []
        record = mock.patch.object(LiveSession, "run", lambda session, draw, keys=None: sessions.append(session))
        with mock.patch("tgju_rates.app.sys.stdout.isatty", return_value=False), record:
            run_live([], [], [], 10, Options(animation="flash", color="always"))
        self.assertTrue(sessions[0].color)
        self.assertEqual(sessions[0].controls.animation, "off")


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


@mock.patch("tgju_rates.app.notify")
@mock.patch("tgju_rates.app.fetch_live_prices", return_value={"current": {}})
class LiveSessionMuteTest(unittest.TestCase):
    def session(self):
        rates = [rate("price_eur", "2,900,000")]
        session = LiveSession(rates, rates, [parse_alert("eur>1")], 10, Options(), color=False)
        session.interactive = True
        return session

    def test_m_clears_alert_lines_and_stops_notifications_until_pressed_again(self, _fetch, notify):
        session = self.session()
        session.poll()
        self.assertEqual(notify.call_count, 1)
        self.assertIn("ALERT", session.frame(0))

        session.controls.handle("m")
        self.assertIn("m unmute alerts", session.key_bar(200))
        frames = []
        session.run(frames.append, FakeKeys([]))
        self.assertNotIn("ALERT", frames[-1])
        self.assertIn("alerts muted", session.title_bar(200))

        session.active_alerts.clear()  # the price crosses the limit again
        session.poll()
        self.assertEqual(notify.call_count, 1)
        self.assertNotIn("ALERT", session.frame(0))

        session.controls.handle("m")
        session.active_alerts.clear()
        session.poll()
        self.assertEqual(notify.call_count, 2)

    def test_mute_hint_only_shows_with_alerts(self, _fetch, _notify):
        session = self.session()
        self.assertIn("m mute alerts", session.key_bar(200))
        session.alerts = []
        self.assertNotIn("mute", session.key_bar(200))


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

    def test_jalali_adds_a_column(self):
        lines = history_csv("price_eur", [(0, 1005)], jalali=True).splitlines()
        self.assertEqual(lines[0], "time,jalali_time,code,price_rial")
        self.assertRegex(lines[1], r",13\d\d/\d\d/\d\d \d\d:\d\d:\d\d,EUR,1005$")


@mock.patch("tgju_rates.app.terminal_width", return_value=80)
@mock.patch("tgju_rates.app.fetch_live_prices", return_value={"current": {}})
class DetailViewTest(unittest.TestCase):
    def run_keys(self, history, *batches):
        rates = [rate("price_eur", "2,900,000"), rate("price_gbp", "3,400,000")]
        session = LiveSession(rates, rates, [parse_alert("gbp>3000000")], 10, Options(), color=False, history=history)
        frames = []
        session.run(frames.append, FakeKeys(*batches))
        return frames

    def test_arrows_and_enter_open_the_selected_rate_with_its_chart(self, _fetch, _width):
        history = History.open(":memory:")
        self.addCleanup(history.close)
        frames = self.run_keys(history, ["\x1b[B", "\x1b[B"], ["\r"], ["d"], ["\x1b"])
        # Frames: the first poll, then one per batch of keys.
        self.assertIn("GBP  British Pound", frames[2])
        self.assertIn("alerts: GBP > 3,000,000", frames[2])
        self.assertIn("GBP (British Pound), last 1 day(s)", frames[2])
        self.assertIn("last 7 day(s)", frames[3])
        self.assertIn("PRICE (RIAL)", frames[4])  # Esc went back to the table

    def test_without_history_says_why_there_is_no_chart(self, _fetch, _width):
        frames = self.run_keys(None, ["\r"])
        self.assertIn("EUR  Euro", frames[1])
        self.assertIn("History is off", frames[1])


if __name__ == "__main__":
    unittest.main()
