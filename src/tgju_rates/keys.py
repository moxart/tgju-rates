"""Read single key presses in live mode without waiting for Enter."""

import os
import re
import select
import sys
import time

try:
    import termios
    import tty
except ImportError:  # Windows
    termios = tty = None

ESCAPE = "\x1b"
# Arrow keys, in the normal and the "application" cursor mode some terminals switch to.
UP_KEYS = ("\x1b[A", "\x1bOA")
DOWN_KEYS = ("\x1b[B", "\x1bOB")
UP_KEY, DOWN_KEY = UP_KEYS[0], DOWN_KEYS[0]
# A CSI sequence ("\x1b[" then parameters and a final letter or ~) or an SS3 one ("\x1bO" and a letter).
SEQUENCE_PATTERN = re.compile(r"\x1b(?:\[[0-9;?]*[@-~]|O[A-Za-z])")
# One key: a known sequence, other Esc text up to the next Esc, or a single character.
KEY_PATTERN = re.compile(rf"{SEQUENCE_PATTERN.pattern}|\x1b[^\x1b]*|.", re.DOTALL)
# Windows reports an arrow as a prefix and a code; these are the codes for up and down.
WINDOWS_ARROWS = {"H": UP_KEY, "P": DOWN_KEY}
# How often Windows checks for a key while waiting; it has no select() on the console.
WINDOWS_POLL_SECONDS = 0.05


def split_keys(text):
    """Split what one read returned into keys.

    Arrow and function keys arrive as an escape sequence such as "\\x1b[A"; each comes back as one
    item, so it can't be mistaken for Esc followed by typed text, and a held arrow key that sent
    several at once gives several items. A sequence can come before or after typed keys in the same
    read. Any other text that starts with Esc stays whole up to the next Esc. A lone "\\x1b" is the Esc key.
    """
    return KEY_PATTERN.findall(text)


class KeyReader:
    """Puts the terminal in cbreak mode (no echo, no line buffering) while in use.

    Ctrl+C still raises KeyboardInterrupt. ``read`` waits up to ``timeout`` seconds (forever if
    None) and returns the keys pressed, or an empty list.
    """

    def __init__(self, stream=None):
        self._stream = stream or sys.stdin
        self._saved = None

    def __enter__(self):
        if termios is not None:
            fd = self._stream.fileno()
            self._saved = termios.tcgetattr(fd)
            tty.setcbreak(fd)
        return self

    def __exit__(self, *exc_info):
        if self._saved is not None:
            termios.tcsetattr(self._stream.fileno(), termios.TCSADRAIN, self._saved)

    def read(self, timeout):
        if termios is None:
            return read_windows(timeout)
        fd = self._stream.fileno()
        ready, _, _ = select.select([fd], [], [], timeout)
        if not ready:
            return []
        return split_keys(os.read(fd, 64).decode(errors="ignore"))


def read_windows(timeout):
    import msvcrt

    deadline = None if timeout is None else time.monotonic() + timeout
    while not msvcrt.kbhit():
        if deadline is not None and time.monotonic() >= deadline:
            return []
        time.sleep(WINDOWS_POLL_SECONDS)
    keys = []
    while msvcrt.kbhit():
        key = msvcrt.getwch()
        if key in ("\x00", "\xe0"):  # arrow and function keys: a prefix and a code
            arrow = WINDOWS_ARROWS.get(msvcrt.getwch())
            if arrow:
                keys.append(arrow)
            continue
        keys.append(key)
    return keys
