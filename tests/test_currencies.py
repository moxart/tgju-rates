import unittest

from tgju_rates.currencies import (
    change_in_toman,
    display_code,
    english_name,
    format_amount,
    parse_change,
    parse_rial,
    rial_to_toman,
    row_key,
    to_toman,
)


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

    def test_rial_to_toman_rounds_toward_zero(self):
        self.assertEqual(rial_to_toman(23505), 2350)
        self.assertEqual(rial_to_toman(-23505), -2350)

    def test_format_amount(self):
        self.assertEqual(format_amount(2584650), "2,584,650 rial")
        self.assertEqual(format_amount(2584650, toman=True), "258,465 toman")


class ChangeTest(unittest.TestCase):
    def test_parse_change(self):
        self.assertEqual(parse_change("(0.4%) 10,050"), (0.4, 10050))
        self.assertEqual(parse_change("(-0.8%) -23,500"), (-0.8, -23500))
        self.assertIsNone(parse_change("-"))
        self.assertIsNone(parse_change("(1.2.3%) 5"))

    def test_change_in_toman(self):
        self.assertEqual(change_in_toman("(-0.8%) -23,500"), "(-0.8%) -2,350")
        self.assertEqual(change_in_toman("(0%) 0"), "(0%) 0")
        self.assertEqual(change_in_toman("n/a"), "n/a")


if __name__ == "__main__":
    unittest.main()
