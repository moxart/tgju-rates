"""Flicker-free terminal output: redraw only the lines that changed since the last frame."""

import shutil
import sys

from tgju_rates.ansi import (
    CLEAR_BELOW,
    CLEAR_LINE_END,
    CLEAR_SCREEN,
    DIM,
    ENTER_LIVE_SCREEN,
    LEAVE_LIVE_SCREEN,
    RESET,
    move_to,
)


class LiveScreen:
    """Keeps the live table in place on screen and rewrites only the lines that changed.

    Use as a context manager: it switches to the terminal's alternate screen on entry and
    restores the normal screen on exit.
    """

    def __init__(self, stream=None, get_size=shutil.get_terminal_size):
        self._stream = stream or sys.stdout
        self._get_size = get_size
        self._drawn = []
        self._size = None

    def __enter__(self):
        self._stream.write(ENTER_LIVE_SCREEN)
        return self

    def __exit__(self, *exc_info):
        self._stream.write(LEAVE_LIVE_SCREEN)
        self._stream.flush()

    def draw(self, lines):
        size = self._get_size()
        out = []
        # After a resize the old screen contents can't be trusted, so start over.
        if size != self._size:
            self._size, self._drawn = size, []
            out.append(CLEAR_SCREEN)
        if len(lines) > size.lines:
            hidden = len(lines) - size.lines + 1
            lines = lines[: size.lines - 1] + [
                f"{DIM}... {hidden} more row(s); enlarge the window or use --watch{RESET}"
            ]
        for row, line in enumerate(lines):
            if row >= len(self._drawn) or self._drawn[row] != line:
                out.append(f"{move_to(row + 1)}{line}{RESET}{CLEAR_LINE_END}")
        if len(lines) < len(self._drawn):
            out.append(f"{move_to(len(lines) + 1)}{CLEAR_BELOW}")
        self._drawn = lines
        self._stream.write("".join(out))
        self._stream.flush()


def print_frame(lines):
    """Piped output can't be redrawn in place, so each frame is appended in full."""
    print("\n".join(lines) + "\n", flush=True)
