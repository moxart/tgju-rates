import unittest
from contextlib import redirect_stderr
from io import StringIO
from unittest import mock

from tgju_rates.ansi import use_color
from tgju_rates.cli import EXIT_INTERRUPTED, build_parser, exit_if_unknown, load_rates, main, parse_watch
from tgju_rates.history import History


def setUpModule():
    # Keep a settings file in the developer's home from changing what main() does here.
    patcher = mock.patch("tgju_rates.cli.default_config_path", return_value="/nonexistent/config.ini")
    patcher.start()
    unittest.addModuleCleanup(patcher.stop)


class CliTest(unittest.TestCase):
    def test_parse_watch_keeps_order_and_drops_duplicates_and_blanks(self):
        self.assertEqual(parse_watch("usd, eur,,USD"), ["price_dollar_rl", "price_eur"])
        self.assertEqual(parse_watch(None), [])

    def test_unknown_codes_exit_with_available_list(self):
        with self.assertRaises(SystemExit) as raised:
            exit_if_unknown({"price_eur": {}, "price_dollar_rl": {}}, ["price_eur", "price_xyz"])
        self.assertIn("Unknown currency code: xyz", str(raised.exception.code))
        self.assertIn("Available: eur, usd", str(raised.exception.code))

    def test_bad_alert_is_a_usage_error(self):
        with redirect_stderr(StringIO()) as stderr, self.assertRaises(SystemExit):
            build_parser().parse_args(["--alert", "usd=5"])
        self.assertIn("is not an alert", stderr.getvalue())

    def test_animation_choices(self):
        self.assertEqual(build_parser().parse_args([]).animation, "flash")
        self.assertEqual(build_parser().parse_args(["--animation", "off"]).animation, "off")
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            build_parser().parse_args(["--animation", "spin"])

    def test_bad_hold_is_a_usage_error(self):
        with redirect_stderr(StringIO()) as stderr, self.assertRaises(SystemExit):
            build_parser().parse_args(["--hold", "usd"])
        self.assertIn("is not a holding", stderr.getvalue())

    def test_market_and_convert_are_checked_when_parsing(self):
        self.assertEqual(build_parser().parse_args(["--market", "gold,coin"]).market, ["gold", "coin"])
        self.assertIsNone(build_parser().parse_args([]).market)
        for argv in (["--market", "stocks"], ["--convert", "usd"]):
            with self.subTest(argv=argv), redirect_stderr(StringIO()), self.assertRaises(SystemExit):
                build_parser().parse_args(argv)

    def test_chart_needs_history(self):
        with redirect_stderr(StringIO()) as stderr, self.assertRaises(SystemExit):
            main(["--chart"])
        self.assertIn("go with --history", stderr.getvalue())

    def test_watching_a_coin_fetches_its_market(self):
        with mock.patch("tgju_rates.cli.load_rates", return_value=({}, "")) as load, self.assertRaises(SystemExit):
            main(["--once", "--no-record", "--watch", "usd,emami"])
        self.assertEqual(load.call_args[0][0], ["currency", "coin"])

    def test_no_alerts_ignores_every_alert(self):
        with mock.patch("tgju_rates.cli.load_rates", return_value=({}, "")):
            with mock.patch("tgju_rates.cli.run_once") as run_once:
                main(["--once", "--no-record", "--alert", "usd>1", "--alert", "total>1", "--no-alerts"])
        self.assertEqual(run_once.call_args[0][2], [])

    def test_dashboard_loads_every_market_unless_market_narrows_it(self):
        for argv, markets in (([], ["currency", "coin", "gold", "crypto"]), (["--market", "coin"], ["coin"])):
            with self.subTest(argv=argv), mock.patch("tgju_rates.cli.load_rates", return_value=({}, "")) as load:
                with mock.patch("tgju_rates.cli.run_once") as run_once:
                    main(["--dashboard", "--once", "--no-record", *argv])
                self.assertEqual(load.call_args[0][0], markets)
                self.assertEqual(run_once.call_args[0][1], [])  # nothing loaded, so nothing shown


class MainErrorsTest(unittest.TestCase):
    def test_unexpected_error_is_a_short_message(self):
        with mock.patch("tgju_rates.cli.run_doctor", side_effect=RuntimeError("boom")):
            with self.assertRaises(SystemExit) as raised:
                main(["--doctor"])
        self.assertIn("unexpected error: RuntimeError: boom", raised.exception.code)
        self.assertIn("--debug", raised.exception.code)

    def test_debug_shows_the_traceback(self):
        with mock.patch("tgju_rates.cli.run_doctor", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                main(["--doctor", "--debug"])

    def test_ctrl_c_exits_with_130(self):
        with mock.patch("tgju_rates.cli.run_doctor", side_effect=KeyboardInterrupt):
            with self.assertRaises(SystemExit) as raised:
                main(["--doctor"])
        self.assertEqual(raised.exception.code, EXIT_INTERRUPTED)


class UseColorTest(unittest.TestCase):
    def check(self, mode, env, tty):
        stream = mock.Mock(isatty=lambda: tty)
        with mock.patch.dict("os.environ", env, clear=True):
            return use_color(mode, stream)

    def test_modes_and_environment(self):
        self.assertTrue(self.check("auto", {}, tty=True))
        self.assertFalse(self.check("auto", {}, tty=False))
        self.assertFalse(self.check("auto", {"NO_COLOR": "1"}, tty=True))
        self.assertFalse(self.check("auto", {"TERM": "dumb"}, tty=True))
        self.assertTrue(self.check("auto", {"FORCE_COLOR": "1"}, tty=False))
        self.assertTrue(self.check("always", {"NO_COLOR": "1"}, tty=False))
        self.assertFalse(self.check("never", {"FORCE_COLOR": "1"}, tty=True))


@mock.patch("tgju_rates.cli.fetch_live_prices", side_effect=OSError("feed down"))
@mock.patch("tgju_rates.cli.load_markets", return_value=({}, {"currency": "could not fetch the page"}))
class LoadRatesFallbackTest(unittest.TestCase):
    def test_uses_saved_prices_when_the_page_fails(self, _load, _fetch):
        history = History.open(":memory:")
        self.addCleanup(history.close)
        history.record([{"key": "price_eur", "price": "3,000,000"}], now=0)

        loaded, notice = load_rates(["currency"], history, ":memory:")
        self.assertEqual([rate["key"] for rate in loaded["currency"]], ["price_eur"])
        self.assertIn("could not fetch the page. Using the list saved in the history file", notice)
        self.assertIn("prices are the last saved ones", notice)

    def test_exits_when_nothing_was_saved(self, _load, _fetch):
        history = History.open(":memory:")
        self.addCleanup(history.close)
        with self.assertRaises(SystemExit) as raised:
            load_rates(["currency"], history, ":memory:")
        self.assertEqual(raised.exception.code, "Could not load currency: could not fetch the page")


if __name__ == "__main__":
    unittest.main()
