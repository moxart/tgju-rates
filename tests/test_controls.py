import unittest

from tgju_rates.controls import LiveControls


def rate(key, price, change="(0%) 0"):
    return {"key": key, "name": "", "price": price, "change": change, "low": "1", "high": "2", "time": ""}


RATES = [
    rate("price_eur", "2,900,000", "(-0.5%) -14,500"),
    rate("price_gbp", "3,400,000", "(1.2%) 40,000"),
    rate("price_aed", "700,000", "(0.1%) 700"),
]


def press(controls, keys):
    for key in keys:
        controls.handle(key)


def codes(rates):
    return [r["key"].removeprefix("price_") for r in rates]


class LiveControlsTest(unittest.TestCase):
    def test_a_cycles_animations_through_off_and_says_so(self):
        controls = LiveControls(animation="board")
        press(controls, "a")
        self.assertEqual(controls.animation, "off")
        self.assertIn("animation: off", controls.describe())
        press(controls, "a")
        self.assertEqual(controls.animation, "flash")

    def test_toggles_toman_and_pause(self):
        controls = LiveControls(toman=True)
        press(controls, "tp")
        self.assertFalse(controls.toman)
        self.assertTrue(controls.paused)
        press(controls, "p")
        self.assertFalse(controls.paused)

    def test_sort_cycles_through_modes(self):
        controls = LiveControls()
        self.assertEqual(codes(controls.apply(RATES)), ["eur", "gbp", "aed"])
        press(controls, "s")
        self.assertEqual(codes(controls.apply(RATES)), ["gbp", "eur", "aed"])  # biggest move, either way
        press(controls, "s")
        self.assertEqual(codes(controls.apply(RATES)), ["gbp", "eur", "aed"])  # price
        press(controls, "s")
        self.assertEqual(codes(controls.apply(RATES)), ["eur", "gbp", "aed"])

    def test_unparseable_values_sort_last(self):
        controls = LiveControls()
        rates = [rate("price_xau", "-", "-"), *RATES]
        press(controls, "s")
        self.assertEqual(codes(controls.apply(rates))[-1], "xau")
        press(controls, "s")
        self.assertEqual(codes(controls.apply(rates))[-1], "xau")

    def test_filter_matches_code_or_english_name(self):
        controls = LiveControls()
        press(controls, "/eu")
        self.assertTrue(controls.editing)
        self.assertEqual(codes(controls.apply(RATES)), ["eur"])
        press(controls, ["\x7f", "\x7f", *"pound", "\r"])
        self.assertFalse(controls.editing)
        self.assertEqual(codes(controls.apply(RATES)), ["gbp"])

    def test_keys_are_typed_into_filter_while_editing(self):
        controls = LiveControls()
        press(controls, "/qtp")
        self.assertEqual(controls.filter, "qtp")
        self.assertFalse(controls.quit or controls.paused or controls.toman)

    def test_escape_clears_filter(self):
        controls = LiveControls()
        press(controls, ["/", "e", "\x1b"])
        self.assertEqual((controls.filter, controls.editing), ("", False))
        press(controls, ["/", "e", "\r", "\x1b"])
        self.assertEqual(controls.filter, "")

    def test_arrow_keys_are_not_typed_into_filter(self):
        controls = LiveControls()
        press(controls, ["/", "\x1b[A", "e"])
        self.assertEqual(controls.filter, "e")

    def test_quit(self):
        controls = LiveControls()
        press(controls, "q")
        self.assertTrue(controls.quit)

    def test_describe(self):
        controls = LiveControls()
        self.assertEqual(controls.describe(), "")
        press(controls, "s/eu")
        self.assertIn("sorted by biggest move", controls.describe())
        self.assertIn("filter: eu_", controls.describe())


if __name__ == "__main__":
    unittest.main()
