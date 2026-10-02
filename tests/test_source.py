import unittest

from tgju_rates.source import apply_live_prices, parse_page_rates

PAGE = """
<table>
  <tr data-market-row="price_eur"><th>یورو</th><td>2,923,500</td><td>(0.5%) 14,500</td>
      <td>2,885,300</td><td>2,926,400</td><td>14:20:01</td><td>chart</td></tr>
  <tr data-market-row="price_eur"><th>duplicate</th><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td></tr>
  <tr data-market-row="price_short"><th>too few cells</th><td>1</td></tr>
  <tr data-market-row="gold_coin"><th>not a currency</th><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td></tr>
  <tr><th>no key</th></tr>
</table>
"""


class ParsePageRatesTest(unittest.TestCase):
    def test_keeps_first_complete_currency_row_per_key(self):
        rates = parse_page_rates(PAGE)

        self.assertEqual([rate["key"] for rate in rates], ["price_eur"])
        self.assertEqual(
            rates[0],
            {
                "key": "price_eur",
                "name": "یورو",
                "price": "2,923,500",
                "change": "(0.5%) 14,500",
                "low": "2,885,300",
                "high": "2,926,400",
                "time": "14:20:01",
            },
        )

    def test_page_without_rows_gives_no_rates(self):
        self.assertEqual(parse_page_rates("<html><body>maintenance</body></html>"), [])


class ApplyLivePricesTest(unittest.TestCase):
    def test_updates_rates_from_feed_and_signs_falling_change(self):
        rates = [{"key": "price_eur", "price": "1", "change": "", "low": "", "high": "", "time": ""}]
        live = {
            "price_eur": {
                "p": "2,900,000",
                "l": "2,880,000",
                "h": "2,950,000",
                "t": "14:30:00",
                "d": "23,500",
                "dp": "0.8",
                "dt": "low",
            }
        }

        apply_live_prices(rates, live)

        self.assertEqual(rates[0]["price"], "2,900,000")
        self.assertEqual(rates[0]["low"], "2,880,000")
        self.assertEqual(rates[0]["high"], "2,950,000")
        self.assertEqual(rates[0]["time"], "14:30:00")
        self.assertEqual(rates[0]["change"], "(-0.8%) -23,500")

    def test_currency_missing_from_feed_is_left_alone(self):
        rates = [{"key": "price_eur", "price": "1"}]
        apply_live_prices(rates, {})
        self.assertEqual(rates[0]["price"], "1")


if __name__ == "__main__":
    unittest.main()
