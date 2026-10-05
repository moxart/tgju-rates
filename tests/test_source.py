import gzip
import unittest
from email.message import Message
from unittest import mock
from urllib.error import HTTPError, URLError

from tgju_rates.source import apply_live_prices, fetch, parse_page_rates

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


class FakeResponse:
    def __init__(self, body, encoding=None):
        self.body = body
        self.headers = Message()
        if encoding:
            self.headers["Content-Encoding"] = encoding

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


@mock.patch("tgju_rates.source.time.sleep")
class FetchTest(unittest.TestCase):
    def test_asks_for_gzip_and_decompresses_it(self, _sleep):
        response = FakeResponse(gzip.compress("سلام".encode()), encoding="gzip")
        with mock.patch("tgju_rates.source.urlopen", return_value=response) as urlopen:
            self.assertEqual(fetch("https://example.test/"), "سلام")
        self.assertEqual(urlopen.call_args[0][0].get_header("Accept-encoding"), "gzip")

    def test_plain_response_is_read_as_is(self, _sleep):
        with mock.patch("tgju_rates.source.urlopen", return_value=FakeResponse(b"{}")):
            self.assertEqual(fetch("https://example.test/"), "{}")

    def test_network_error_is_retried_once(self, sleep):
        attempts = [URLError("reset"), FakeResponse(b"ok")]
        with mock.patch("tgju_rates.source.urlopen", side_effect=attempts):
            self.assertEqual(fetch("https://example.test/"), "ok")
        sleep.assert_called_once()

    def test_gives_up_after_the_last_attempt(self, _sleep):
        with mock.patch("tgju_rates.source.urlopen", side_effect=URLError("down")) as urlopen:
            with self.assertRaises(URLError):
                fetch("https://example.test/", attempts=3)
        self.assertEqual(urlopen.call_count, 3)

    def test_http_error_is_not_retried(self, sleep):
        error = HTTPError("https://example.test/", 403, "Forbidden", Message(), None)
        with mock.patch("tgju_rates.source.urlopen", side_effect=error) as urlopen:
            with self.assertRaises(HTTPError):
                fetch("https://example.test/")
        self.assertEqual(urlopen.call_count, 1)
        sleep.assert_not_called()

    def test_truncated_gzip_is_a_network_error(self, _sleep):
        broken = FakeResponse(gzip.compress(b"x" * 100)[:-10], encoding="gzip")
        with mock.patch("tgju_rates.source.urlopen", return_value=broken):
            with self.assertRaises(OSError):
                fetch("https://example.test/", attempts=1)


if __name__ == "__main__":
    unittest.main()
