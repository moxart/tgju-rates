import json
import unittest

from tgju_rates.export import history_json, rate_record, rates_json
from tgju_rates.holdings import Holding, value_holdings

RATE = {
    "key": "price_eur",
    "name": "یورو",
    "price": "2,923,500",
    "change": "(-0.5%) -14,505",
    "low": "2,885,300",
    "high": "-",
    "time": "14:20:01",
}


class ExportTest(unittest.TestCase):
    def test_rate_record_in_rial(self):
        self.assertEqual(
            rate_record(RATE),
            {
                "code": "EUR",
                "key": "price_eur",
                "name": "Euro",
                "persian_name": "یورو",
                "price": 2923500,
                "change": -14505,
                "change_percent": -0.5,
                "low": 2885300,
                "high": None,
                "updated": "14:20:01",
            },
        )

    def test_rate_record_in_toman_rounds_toward_zero(self):
        record = rate_record(RATE, toman=True)
        self.assertEqual((record["price"], record["change"], record["low"]), (292350, -1450, 288530))

    def test_snapshot_is_one_line_with_unit_and_alerts(self):
        text = rates_json([RATE], now=0, toman=True, alerts=["EUR is ..."])
        self.assertNotIn("\n", text)
        data = json.loads(text)
        self.assertEqual(data["unit"], "toman")
        self.assertEqual(data["alerts"], ["EUR is ..."])
        self.assertEqual(data["rates"][0]["code"], "EUR")
        self.assertNotIn("holdings", data)

    def test_snapshot_with_holdings(self):
        valuation = value_holdings([Holding("price_eur", 2, 2000000)], [RATE])
        data = json.loads(rates_json([RATE], now=0, toman=True, valuation=valuation))
        self.assertEqual(
            data["holdings"],
            {
                "items": [
                    {
                        "code": "EUR",
                        "amount": 2,
                        "cost": 200000,
                        "worth": 584700,
                        "gain_percent": 46.17,
                        "today": -2901,
                        "today_percent": -0.5,
                    }
                ],
                "worth": 584700,
                "gain_percent": 46.17,
                "today": -2901,
                "today_percent": -0.49,
            },
        )

    def test_history_json(self):
        data = json.loads(history_json("price_eur", [(0, 1000)], toman=True))
        self.assertEqual(data["code"], "EUR")
        self.assertEqual(data["prices"][0]["price"], 100)


if __name__ == "__main__":
    unittest.main()
