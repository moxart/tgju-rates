import unittest
from unittest import mock

from tgju_rates.convert import (
    Conversion,
    convert,
    format_conversion,
    parse_conversion,
    quick_conversion,
    run_convert,
)
from tgju_rates.history import History

PRICES = {"price_dollar_rl": 2_500_000, "price_eur": 3_000_000, "price_jpy": 1_700_000, "crypto-bitcoin-irr": 10**11}


class ParseConversionTest(unittest.TestCase):
    def test_forms(self):
        self.assertEqual(parse_conversion("250 usd"), Conversion(250, "price_dollar_rl"))
        self.assertEqual(parse_conversion("1.5 usd eur"), Conversion(1.5, "price_dollar_rl", "price_eur"))
        self.assertEqual(parse_conversion("50,000,000 toman to btc"), Conversion(50e6, "toman", "crypto-bitcoin-irr"))
        self.assertEqual(parse_conversion("10 eur in IRR"), Conversion(10, "price_eur", "rial"))

    def test_rejects_nonsense(self):
        for text in ("usd 250", "250", "250 toman", "1 usd eur gbp", ""):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_conversion(text)


class ConvertTest(unittest.TestCase):
    def test_to_rial_and_toman_by_default(self):
        self.assertEqual(convert(Conversion(2, "price_dollar_rl"), PRICES), {"rial": 5_000_000, "toman": 500_000})

    def test_between_currencies(self):
        self.assertAlmostEqual(convert(Conversion(3, "price_eur", "price_dollar_rl"), PRICES)["price_dollar_rl"], 3.6)

    def test_yen_is_priced_per_hundred(self):
        self.assertEqual(convert(Conversion(1000, "price_jpy", "rial"), PRICES), {"rial": 17_000_000})

    def test_format_names_usd_and_lists_prices(self):
        conversion = Conversion(50e6, "toman", "crypto-bitcoin-irr")
        text = format_conversion(conversion, convert(conversion, PRICES), PRICES)
        self.assertEqual(text.splitlines()[0], "50,000,000 toman = 0.005 BTC")
        text = format_conversion(Conversion(2, "price_dollar_rl"), {"rial": 5e6, "toman": 5e5}, PRICES)
        self.assertEqual(text.splitlines()[0], "2 USD = 5,000,000 rial = 500,000 toman")
        self.assertIn("1 USD (US Dollar) = 2,500,000 rial", text)


class QuickConversionTest(unittest.TestCase):
    def test_result_hint_and_missing_market(self):
        self.assertEqual(quick_conversion("2 usd", PRICES), "2 USD = 5,000,000 rial = 500,000 toman")
        self.assertIn("type e.g.", quick_conversion("2 ", PRICES))
        self.assertEqual(quick_conversion("1 emami", PRICES), "no price for emami (add --market coin)")
        self.assertEqual(quick_conversion("1 xyz", PRICES), "no price for xyz")


class RunConvertTest(unittest.TestCase):
    @mock.patch("tgju_rates.convert.fetch_live_prices", side_effect=OSError("offline"))
    def test_falls_back_to_saved_prices(self, _fetch):
        history = History.open(":memory:")
        self.addCleanup(history.close)
        history.record([{"key": "price_eur", "price": "3,000,000"}], now=0)
        with mock.patch("builtins.print") as printed:
            self.assertIsNone(run_convert("2 eur", history))
        output = printed.call_args[0][0]
        self.assertIn("2 EUR = 6,000,000 rial", output)
        self.assertIn("Feed unavailable (offline); using saved prices", output)

    @mock.patch("tgju_rates.convert.fetch_live_prices", return_value={"price_eur": {"p": "3,000,000"}})
    def test_unknown_code_is_an_error(self, _fetch):
        self.assertEqual(run_convert("2 xyz"), "No price for xyz.")

    @mock.patch("tgju_rates.convert.fetch_live_prices", return_value={"price_eur": {"p": "0"}})
    def test_zero_price_is_missing_not_a_division_by_zero(self, _fetch):
        self.assertEqual(run_convert("2 toman eur"), "No price for eur.")


if __name__ == "__main__":
    unittest.main()
