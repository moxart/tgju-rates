import unittest

from tgju_rates.alerts import Alert, check_alerts, parse_alert


def rates_at(price):
    return [{"key": "price_dollar_rl", "price": f"{price:,}"}]


class ParseAlertTest(unittest.TestCase):
    def test_parses_code_operator_and_limit_with_commas(self):
        self.assertEqual(parse_alert("usd >= 2,600,000"), Alert("price_dollar_rl", ">=", 2600000))

    def test_toman_limit_is_stored_in_rial(self):
        self.assertEqual(parse_alert("usd>260,000", toman=True), Alert("price_dollar_rl", ">", 2600000))

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

    def test_message_in_toman(self):
        [message] = check_alerts([parse_alert("usd<200", toman=True)], rates_at(1500), set(), toman=True)
        self.assertEqual(message, "DOLLAR_RL is 150 toman  (alert: DOLLAR_RL < 200)")

    def test_currency_without_price_is_skipped(self):
        alerts = [parse_alert("eur>1")]
        self.assertEqual(check_alerts(alerts, rates_at(150), set()), [])


class TotalAlertTest(unittest.TestCase):
    def test_parses_total(self):
        self.assertEqual(parse_alert("TOTAL>5,000", toman=True), Alert("total", ">", 50000))

    def test_checks_total_and_skips_it_when_unknown(self):
        alert = parse_alert("total>100")
        self.assertEqual(check_alerts([alert], rates_at(1), set(), total=None), [])
        self.assertEqual(
            check_alerts([alert], rates_at(1), set(), total=150), ["TOTAL is 150 rial  (alert: TOTAL > 100)"]
        )


if __name__ == "__main__":
    unittest.main()
