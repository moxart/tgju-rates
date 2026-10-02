import unittest

from tgju_rates.currencies import display_code, english_name, parse_rial, row_key, to_toman


class CurrencyCodeTest(unittest.TestCase):
    def test_row_key_normalises_and_resolves_usd_alias(self):
        self.assertEqual(row_key(" EUR "), "price_eur")
        self.assertEqual(row_key("usd"), "price_dollar_rl")

    def test_display_code(self):
        self.assertEqual(display_code("price_gbp"), "GBP")

    def test_unknown_currency_has_placeholder_name(self):
        self.assertEqual(english_name("price_eur"), "Euro")
        self.assertEqual(english_name("price_xyz"), "-")


class RialTest(unittest.TestCase):
    def test_parse_rial(self):
        self.assertEqual(parse_rial("2,584,650"), 2584650)
        self.assertIsNone(parse_rial("-"))
        self.assertIsNone(parse_rial(""))

    def test_to_toman(self):
        self.assertEqual(to_toman("2,584,650"), "258,465")
        self.assertEqual(to_toman("n/a"), "-")


if __name__ == "__main__":
    unittest.main()
