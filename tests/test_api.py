import json
import threading
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import urlopen

from tgju_rates.api import Api, RateStore
from tgju_rates.history import History
from tgju_rates.server import bind, serve

NOW = 1_760_000_000.0


def row(key, price, change="(0.5%) 1,000"):
    return {"key": key, "name": "", "price": price, "change": change, "low": "-", "high": "-", "time": "14:20:01"}


def sample_rates():
    return [
        row("price_dollar_rl", "1,100,000"),
        row("price_eur", "1,300,000", "(-0.8%) -10,500"),
        row("sekee", "1,000,000,000"),
        row("geram18", "100,000,000"),
    ]


def make_store(history=None, updated_at=NOW):
    store = RateStore(sample_rates(), interval=10, history=history, clock=lambda: NOW)
    store.updated_at = updated_at
    return store


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.history = History.open(":memory:")
        self.api = Api(make_store(self.history))

    def tearDown(self):
        self.history.close()

    def get(self, path, **params):
        return self.api.handle(path, params)

    def test_index_lists_endpoints(self):
        for path in ("/", "/v1", "/v1/"):
            status, payload = self.get(path)
            self.assertEqual(status, 200)
            self.assertIn("GET /v1/health", payload["endpoints"])

    def test_rates_are_numbers_with_freshness(self):
        status, payload = self.get("/v1/rates")
        self.assertEqual(status, 200)
        self.assertEqual(payload["unit"], "rial")
        self.assertFalse(payload["stale"])
        self.assertEqual([rate["code"] for rate in payload["rates"]], ["USD", "EUR", "EMAMI", "GOLD18"])
        self.assertEqual(payload["rates"][1]["change"], -10500)

    def test_rates_by_market_codes_and_unit(self):
        _, payload = self.get("/v1/rates", market="coin")
        self.assertEqual([rate["key"] for rate in payload["rates"]], ["sekee"])
        _, payload = self.get("/v1/rates", codes="eur,usd", unit="toman")
        self.assertEqual([rate["price"] for rate in payload["rates"]], [130_000, 110_000])
        self.assertEqual(payload["unit"], "toman")

    def test_one_rate(self):
        status, payload = self.get("/v1/rates/usd")
        self.assertEqual((status, payload["rate"]["price"]), (200, 1_100_000))
        status, payload = self.get("/v1/rates/EMAMI")
        self.assertEqual((status, payload["rate"]["key"]), (200, "sekee"))

    def test_bad_requests(self):
        cases = [
            ("/v1/rates/xyz", {}, 404),
            ("/v1/rates", {"codes": "usd,xyz"}, 404),
            ("/v1/rates", {"market": "nope"}, 400),
            ("/v1/rates", {"unit": "dollar"}, 400),
            ("/v1/nothing", {}, 404),
            ("/v2/rates", {}, 404),
            ("/v1/rates/usd/more", {}, 404),
            ("/v1/history/usd", {"days": "0"}, 400),
            ("/v1/history/usd", {"days": "-1"}, 400),
            ("/v1/convert", {"amount": "abc", "from": "usd"}, 400),
            ("/v1/convert", {"amount": "nan", "from": "usd"}, 400),
            ("/v1/convert", {"amount": "1e308", "from": "usd"}, 400),
            ("/v1/jewelry", {"weight": "1", "wage": "1e308"}, 400),
            ("/v1/convert", {"amount": "5"}, 400),
            ("/v1/convert", {"amount": "5", "from": "toman"}, 400),
            ("/v1/convert", {"amount": "5", "from": "xyz"}, 404),
            ("/v1/jewelry", {"weight": "0"}, 400),
            ("/v1/jewelry", {}, 400),
        ]
        for path, params, expected in cases:
            with self.subTest(path=path, params=params):
                status, payload = self.api.handle(path, params)
                self.assertEqual(status, expected)
                self.assertIn("error", payload)

    def test_history(self):
        self.history.record([row("price_dollar_rl", "1,000,000")], NOW - 2 * 86400)
        self.history.record([row("price_dollar_rl", "1,050,000")], NOW - 3600)
        status, payload = self.get("/v1/history/usd", unit="toman")
        self.assertEqual(status, 200)
        self.assertEqual([point["price"] for point in payload["prices"]], [105_000])
        _, payload = self.get("/v1/history/usd", days="7")
        self.assertEqual([point["price"] for point in payload["prices"]], [1_000_000, 1_050_000])

    def test_history_off(self):
        status, _ = Api(make_store()).handle("/v1/history/usd", {})
        self.assertEqual(status, 503)

    def test_convert_uses_polled_prices(self):
        status, payload = self.get("/v1/convert", amount="13", **{"from": "eur", "to": "usd"})
        self.assertEqual(status, 200)
        self.assertAlmostEqual(payload["results"]["USD"], 13 * 1_300_000 / 1_100_000)
        _, payload = self.get("/v1/convert", amount="2", **{"from": "usd"})
        self.assertEqual(payload["results"], {"rial": 2_200_000, "toman": 220_000})

    def test_jewelry(self):
        status, payload = self.get("/v1/jewelry", weight="10", wage="20%")
        self.assertEqual(status, 200)
        self.assertEqual(payload["parts_rial"]["gold"], 1_000_000_000)
        self.assertEqual(payload["percents"], {"wage": 20.0, "profit": 7.0, "tax": 10.0})

    def test_health_turns_stale(self):
        _, payload = self.get("/v1/health")
        self.assertEqual((payload["status"], payload["history"]), ("ok", True))
        _, payload = Api(make_store(updated_at=NOW - 60)).handle("/v1/health", {})
        self.assertEqual(payload["status"], "stale")
        _, payload = Api(make_store(updated_at=None)).handle("/v1/health", {})
        self.assertEqual((payload["status"], payload["updated"]), ("stale", None))


class RateStoreTest(unittest.TestCase):
    @mock.patch("tgju_rates.api.fetch_live_prices")
    def test_poll_applies_prices_and_records(self, fetch):
        fetch.return_value = {"price_eur": {"p": "1,400,000", "l": "1", "h": "2", "t": "15:00", "d": "5", "dp": "1"}}
        history = History.open(":memory:")
        store = make_store(history, updated_at=None)
        store.poll()
        self.assertEqual(store.rates[1]["price"], "1,400,000")
        self.assertEqual((store.updated_at, store.error), (NOW, None))
        self.assertEqual(history.latest()["price_eur"], (NOW, 1_400_000))
        history.close()

    @mock.patch("tgju_rates.api.fetch_live_prices", side_effect=OSError("offline"))
    def test_failed_poll_backs_off_and_keeps_prices(self, _fetch):
        store = make_store()
        store.poll()
        store.poll()
        self.assertEqual(store.failures, 2)
        self.assertEqual(store.poll_delay(), 40)
        self.assertIn("offline", store.error)
        self.assertEqual(store.updated_at, NOW)


class ServerTest(unittest.TestCase):
    @mock.patch("tgju_rates.api.fetch_live_prices", return_value={})
    def test_serves_json_over_http(self, _fetch):
        server = bind("127.0.0.1", 0)
        thread = threading.Thread(target=serve, args=(server, make_store()), daemon=True)
        with mock.patch("sys.stderr"):
            thread.start()
            base = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                with urlopen(f"{base}/v1/rates/usd?unit=toman") as response:
                    self.assertEqual(response.headers["Content-Type"], "application/json; charset=utf-8")
                    self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")
                    self.assertEqual(json.load(response)["rate"]["price"], 110_000)
                with self.assertRaises(HTTPError) as caught:
                    urlopen(f"{base}/v1/rates/xyz")
                self.assertEqual(caught.exception.code, 404)
                self.assertIn("unknown code", json.load(caught.exception)["error"])
                caught.exception.close()
                with mock.patch.object(server.api, "handle", side_effect=RuntimeError("secret detail")):
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(f"{base}/v1/rates")
                self.assertEqual(caught.exception.code, 500)
                self.assertEqual(json.load(caught.exception), {"error": "internal error"})
                caught.exception.close()
            finally:
                server.shutdown()
                thread.join()


if __name__ == "__main__":
    unittest.main()
