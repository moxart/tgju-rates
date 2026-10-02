import io
import os
import unittest

from tgju_rates.ansi import CLEAR_SCREEN, ENTER_LIVE_SCREEN, LEAVE_LIVE_SCREEN, move_to
from tgju_rates.screen import LiveScreen


class FakeTerminal:
    def __init__(self, columns=80, lines=24):
        self.size = os.terminal_size((columns, lines))

    def __call__(self):
        return self.size


class LiveScreenTest(unittest.TestCase):
    def setUp(self):
        self.out = io.StringIO()
        self.terminal = FakeTerminal()
        self.screen = LiveScreen(stream=self.out, get_size=self.terminal)

    def drawn(self, lines):
        self.out.seek(0)
        self.out.truncate()
        self.screen.draw(lines)
        return self.out.getvalue()

    def test_first_frame_clears_and_draws_every_line(self):
        output = self.drawn(["a", "b"])
        self.assertTrue(output.startswith(CLEAR_SCREEN))
        self.assertIn(move_to(1) + "a", output)
        self.assertIn(move_to(2) + "b", output)

    def test_later_frames_rewrite_only_changed_lines(self):
        self.drawn(["a", "b", "c"])
        output = self.drawn(["a", "B", "c"])

        self.assertNotIn(CLEAR_SCREEN, output)
        self.assertIn(move_to(2) + "B", output)
        self.assertNotIn(move_to(1), output)
        self.assertNotIn(move_to(3), output)

    def test_unchanged_frame_writes_nothing(self):
        self.drawn(["a"])
        self.assertEqual(self.drawn(["a"]), "")

    def test_shorter_frame_clears_leftover_lines(self):
        self.drawn(["a", "b", "c"])
        self.assertIn(move_to(2) + "\033[J", self.drawn(["a"]))

    def test_resize_forces_full_redraw(self):
        self.drawn(["a"])
        self.terminal.size = os.terminal_size((100, 30))
        self.assertTrue(self.drawn(["a"]).startswith(CLEAR_SCREEN))

    def test_frame_taller_than_terminal_is_cut_with_note(self):
        self.terminal.size = os.terminal_size((80, 3))
        output = self.drawn(["1", "2", "3", "4", "5"])

        self.assertIn(move_to(2) + "2", output)
        self.assertNotIn(move_to(4), output)
        self.assertIn("3 more row(s)", output)

    def test_context_manager_restores_terminal(self):
        with self.screen:
            pass
        self.assertEqual(self.out.getvalue(), ENTER_LIVE_SCREEN + LEAVE_LIVE_SCREEN)


if __name__ == "__main__":
    unittest.main()
