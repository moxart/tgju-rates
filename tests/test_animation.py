import unittest

from tgju_rates.animation import ANIMATION_SECONDS, ROLL_SHARE, cell_style, rolled


class CellStyleTest(unittest.TestCase):
    def test_flash_fades_its_background(self):
        start = cell_style("flash", "up", 0)
        later = cell_style("flash", "up", ANIMATION_SECONDS * 0.9)
        self.assertIn("48;5;34", start)
        self.assertNotEqual(start, later)
        self.assertIn("48;5;160", cell_style("flash", "down", 0))

    def test_glow_colours_text_only(self):
        style = cell_style("glow", "down", 0)
        self.assertIn("38;5;", style)
        self.assertNotIn("48;5;", style)

    def test_nothing_plays_once_finished_or_off(self):
        self.assertIsNone(cell_style("flash", "up", ANIMATION_SECONDS))
        self.assertIsNone(cell_style("off", "up", 0))
        self.assertIsNone(cell_style("roll", "up", 0))


class RolledTest(unittest.TestCase):
    def test_only_changed_digits_spin(self):
        text = rolled("3,014,200", "3,016,450", 0)
        self.assertEqual(len(text), len("3,016,450"))
        self.assertEqual(text[:4] + text[5] + text[-1], "3,01,0")
        for index in (4, 6, 7):
            self.assertNotEqual(text[index], "3,016,450"[index])

    def test_digits_settle_left_to_right(self):
        span = ANIMATION_SECONDS * ROLL_SHARE
        self.assertTrue(rolled("3,014,200", "3,016,450", span / 3).startswith("3,016,"))
        self.assertEqual(rolled("3,014,200", "3,016,450", span), "3,016,450")

    def test_a_longer_number_keeps_its_width(self):
        self.assertEqual(len(rolled("999,000", "1,000,000", 0)), len("1,000,000"))
        self.assertEqual(rolled("999,000", "1,000,000", ANIMATION_SECONDS), "1,000,000")
