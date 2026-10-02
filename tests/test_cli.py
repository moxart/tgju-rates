import unittest
from contextlib import redirect_stderr
from io import StringIO

from tgju_rates.cli import build_parser, exit_if_unknown, parse_watch


class CliTest(unittest.TestCase):
    def test_parse_watch_keeps_order_and_drops_duplicates_and_blanks(self):
        self.assertEqual(parse_watch("usd, eur,,USD"), ["price_dollar_rl", "price_eur"])
        self.assertEqual(parse_watch(None), [])

    def test_unknown_codes_exit_with_available_list(self):
        with self.assertRaises(SystemExit) as raised:
            exit_if_unknown({"price_eur": {}}, ["price_eur", "price_xyz"])
        self.assertIn("Unknown currency code: xyz", str(raised.exception.code))
        self.assertIn("Available: eur, usd", str(raised.exception.code))

    def test_bad_alert_is_a_usage_error(self):
        with redirect_stderr(StringIO()) as stderr, self.assertRaises(SystemExit):
            build_parser().parse_args(["--alert", "usd=5"])
        self.assertIn("is not an alert", stderr.getvalue())

    def test_bad_hold_is_a_usage_error(self):
        with redirect_stderr(StringIO()) as stderr, self.assertRaises(SystemExit):
            build_parser().parse_args(["--hold", "usd"])
        self.assertIn("is not a holding", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
