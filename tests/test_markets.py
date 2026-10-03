import unittest
from unittest import mock

from tgju_rates.currencies import display_code, english_name, known_codes, row_key
from tgju_rates.markets import CURRENCY, market_of, parse_markets
from tgju_rates.source import feed_market_rates, load_markets


def feed_item(price, change="0", percent=0, direction=""):
    return {"p": price, "l": price, "h": price, "t": "12:00", "d": change, "dp": percent, "dt": direction}


class MarketsTest(unittest.TestCase):
    def test_parse_markets(self):
        self.assertEqual(parse_markets("gold, coin,gold"), ["gold", "coin"])
        self.assertEqual(parse_markets("all"), ["currency", "coin", "gold", "crypto"])
        with self.assertRaisesRegex(ValueError, "unknown market silver"):
            parse_markets("coin,silver")
        with self.assertRaises(ValueError):
            parse_markets(" , ")

    def test_codes_of_feed_instruments(self):
        self.assertEqual(row_key("Emami"), "sekee")
        self.assertEqual(row_key("sekee"), "sekee")  # the feed's own key works too
        self.assertEqual(row_key("btc"), "crypto-bitcoin-irr")
        self.assertEqual(row_key("eur"), "price_eur")
        self.assertEqual(display_code("crypto-bitcoin-irr"), "BTC")
        self.assertEqual(english_name("geram18"), "18k Gold (gram)")
        self.assertEqual(market_of("sekee"), "coin")
        self.assertEqual(market_of("price_eur"), CURRENCY)

    def test_known_codes_use_usd_not_the_site_key(self):
        codes = known_codes()
        self.assertIn("usd", codes)
        self.assertIn("emami", codes)
        self.assertNotIn("dollar_rl", codes)


class FeedMarketRatesTest(unittest.TestCase):
    def test_builds_rows_in_listed_order_and_skips_missing(self):
        live = {"sekeb": feed_item("2,600,000,000"), "sekee": feed_item("2,700,000,000", "1,000", 0.1, "low")}
        rates = feed_market_rates(["coin"], live)
        self.assertEqual([rate["key"] for rate in rates], ["sekee", "sekeb"])
        self.assertEqual(rates[0]["name"], "سکه امامی")
        self.assertEqual(rates[0]["price"], "2,700,000,000")
        self.assertEqual(rates[0]["change"], "(-0.1%) -1,000")

    @mock.patch("tgju_rates.source.fetch_live_prices", return_value={"sekee": feed_item("1")})
    @mock.patch("tgju_rates.source.scrape_page_rates", side_effect=OSError("down"))
    def test_one_failing_source_doesnt_stop_the_other(self, _scrape, _fetch):
        loaded, errors = load_markets(["currency", "coin", "gold"])
        self.assertEqual(list(loaded), ["coin"])
        self.assertIn("down", errors["currency"])
        self.assertEqual(errors["gold"], "the feed has no gold prices")

    @mock.patch("tgju_rates.source.scrape_page_rates", return_value=[])
    def test_empty_page_is_a_failure(self, _scrape):
        loaded, errors = load_markets(["currency"])
        self.assertEqual(loaded, {})
        self.assertIn("layout may have changed", errors["currency"])


if __name__ == "__main__":
    unittest.main()
