import json
import unittest
from io import StringIO
from unittest import mock

from tgju_rates.history import History
from tgju_rates.jewelry import Piece, format_quote, parse_piece, quote, run_jewelry


class ParsePieceTest(unittest.TestCase):
    def test_forms(self):
        self.assertEqual(parse_piece("12.5g"), Piece(12.5))
        self.assertEqual(parse_piece("12.5 grams wage 18%"), Piece(12.5, wage=18))
        self.assertEqual(parse_piece("8 g WAGE 20 profit 5% tax 9%"), Piece(8, wage=20, profit=5, tax=9))

    def test_rejects_nonsense(self):
        for text in ("", "wage 18%", "0g", "-3g", "12g wage", "12g wage x%", "12g discount 5%"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_piece(text)


class QuoteTest(unittest.TestCase):
    def test_follows_the_shop_formula(self):
        result = quote(Piece(10, wage=20, profit=7, tax=10), gram_price=200_000_000)
        self.assertEqual(result.gold, 2_000_000_000)
        self.assertEqual(result.wage, 400_000_000)
        self.assertEqual(result.profit, 168_000_000)  # 7% of gold plus wage
        self.assertEqual(result.tax, 56_800_000)  # 10% of wage plus profit, not of the gold
        self.assertEqual(result.total, 2_624_800_000)

    def test_parts_are_whole_toman_so_both_columns_add_up(self):
        result = quote(Piece(3.37, wage=17.5), gram_price=263_756_123)
        parts = (result.gold, result.wage, result.profit, result.tax)
        self.assertTrue(all(part % 10 == 0 for part in parts))
        self.assertEqual(sum(parts), result.total)

    def test_format_leads_with_the_chosen_unit(self):
        result = quote(Piece(1, wage=10), gram_price=100_000_000)
        self.assertIn("at 100,000,000 rial per gram", format_quote(result))
        text = format_quote(result, toman=True)
        self.assertIn("at 10,000,000 toman per gram", text)
        self.assertRegex(text, r"Total\s+11,947,000\s+119,470,000")


class RunJewelryTest(unittest.TestCase):
    @mock.patch("tgju_rates.convert.fetch_live_prices", return_value={"geram18": {"p": "200,000,000"}})
    def test_json_from_the_feed(self, _fetch):
        with mock.patch("sys.stdout", new_callable=StringIO) as out:
            self.assertIsNone(run_jewelry("10g wage 20%", as_json=True))
        data = json.loads(out.getvalue())
        self.assertEqual(data["total_rial"], 2_624_800_000)
        self.assertIsNone(data["note"])

    @mock.patch("tgju_rates.convert.fetch_live_prices", side_effect=OSError("offline"))
    def test_falls_back_to_saved_price_and_errors_without_one(self, _fetch):
        history = History.open(":memory:")
        self.addCleanup(history.close)
        self.assertIn("No price for gold18", run_jewelry("10g", history))
        history.record([{"key": "geram18", "price": "200,000,000"}], now=0)
        with mock.patch("sys.stdout", new_callable=StringIO) as out:
            self.assertIsNone(run_jewelry("10g", history))
        self.assertIn("Feed unavailable (offline); using saved prices", out.getvalue())


if __name__ == "__main__":
    unittest.main()
