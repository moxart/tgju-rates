import unittest
from unittest import mock

from tgju_rates.alerts import parse_alert
from tgju_rates.app import LiveSession, Options
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


if __name__ == "__main__":
    unittest.main()
