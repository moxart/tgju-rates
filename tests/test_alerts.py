import unittest

from tgju_rates.alerts import Alert, check_alerts, parse_alert


def rates_at(price):
    return [{"key": "price_dollar_rl", "price": f"{price:,}"}]


class ParseAlertTest(unittest.TestCase):
    def test_parses_code_operator_and_limit_with_commas(self):
        self.assertEqual(parse_alert("usd >= 2,600,000"), Alert("price_dollar_rl", ">=", 2600000))

    def test_rejects_malformed_rule(self):
        for text in ("usd", "usd=>5", "usd > abc", ">5"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_alert(text)


class CheckAlertsTest(unittest.TestCase):
    def test_fires_once_then_rearms_after_condition_clears(self):
        alerts = [parse_alert("usd>100")]
        active = set()

        self.assertEqual(len(check_alerts(alerts, rates_at(150), active)), 1)
        self.assertEqual(check_alerts(alerts, rates_at(160), active), [])  # still true: no repeat
        self.assertEqual(check_alerts(alerts, rates_at(90), active), [])  # cleared: re-armed
        self.assertEqual(len(check_alerts(alerts, rates_at(120), active)), 1)

    def test_message_names_currency_and_price(self):
        [message] = check_alerts([parse_alert("usd<200")], rates_at(150), set())
        self.assertEqual(message, "DOLLAR_RL is 150 rial  (alert: DOLLAR_RL < 200)")

    def test_currency_without_price_is_skipped(self):
        alerts = [parse_alert("eur>1")]
        self.assertEqual(check_alerts(alerts, rates_at(150), set()), [])


if __name__ == "__main__":
    unittest.main()
