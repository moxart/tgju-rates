import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from tgju_rates.doctor import FAIL, OK, WARN, check_feed_entries, run_doctor
from tgju_rates.markets import FEED_MARKETS

ITEM = {"p": "1,000", "l": "1", "h": "2", "d": "0", "dp": 0}


def full_feed():
    return {"price_eur": ITEM, **{item.key: ITEM for items in FEED_MARKETS.values() for item in items}}


class DoctorTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)

    def run_doctor(self):
        with redirect_stdout(StringIO()) as out:
            code = run_doctor(self.folder / "history.db", self.folder / "holdings.txt", self.folder / "config.ini")
        return code, out.getvalue()

    @mock.patch("tgju_rates.doctor.fetch_live_prices", side_effect=full_feed)
    @mock.patch("tgju_rates.doctor.scrape_page_rates", return_value=[{"key": "price_eur"}, {"key": "price_xyz"}])
    def test_healthy_site_passes_with_a_warning_for_unnamed_currencies(self, _scrape, _fetch):
        code, out = self.run_doctor()
        self.assertEqual(code, 0)
        self.assertIn("ok    currency page: 2 currencies", out)
        self.assertIn("warn  currencies without an English name (shown as '-'): xyz", out)
        self.assertIn("currencies: 1/2 in the feed; missing: xyz", out)
        self.assertIn("ok    coin: 5/5 in the feed", out)
        self.assertIn("history: no file yet", out)
        self.assertIn("ok    settings: none", out)

    @mock.patch("tgju_rates.doctor.fetch_live_prices", side_effect=full_feed)
    @mock.patch("tgju_rates.doctor.scrape_page_rates", return_value=[{"key": "price_eur"}])
    def test_reports_the_settings_file(self, _scrape, _fetch):
        (self.folder / "config.ini").write_text("[defaults]\ntoman = yes\n")
        self.assertIn("ok    settings: toman from", self.run_doctor()[1])
        (self.folder / "config.ini").write_text("[defaults]\nonce = yes\n")
        code, out = self.run_doctor()
        self.assertEqual(code, 1)
        self.assertIn("FAIL  settings:", out)
        self.assertIn("unknown option 'once'", out)

    @mock.patch("tgju_rates.doctor.fetch_live_prices", side_effect=OSError("no route"))
    @mock.patch("tgju_rates.doctor.scrape_page_rates", return_value=[])
    def test_broken_page_and_feed_fail(self, _scrape, _fetch):
        (self.folder / "holdings.txt").write_text("usd=oops\n")
        code, out = self.run_doctor()
        self.assertEqual(code, 1)
        self.assertIn("FAIL  currency page: no rows found", out)
        self.assertIn("FAIL  feed: could not read", out)
        self.assertIn("FAIL  holdings:", out)

    def test_feed_entries(self):
        live = {"a": ITEM, "b": {"p": "4,140.19", "l": "1", "h": "2", "d": "0", "dp": 0}}
        self.assertEqual(check_feed_entries(["a"], live, "x"), [(OK, "x: 1/1 in the feed")])
        [(status, line)] = check_feed_entries(["a", "b", "price_c"], live, "x")
        self.assertEqual(status, WARN)
        self.assertIn("missing: c; unexpected format: b", line)
        self.assertEqual(check_feed_entries(["price_c"], live, "x")[0][0], FAIL)


if __name__ == "__main__":
    unittest.main()
