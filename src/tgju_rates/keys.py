"""Read single key presses in live mode without waiting for Enter."""

import os
import select
import sys
import time

try:
    import termios
    import tty
except ImportError:  # Windows
    termios = tty = None

ESCAPE = "\x1b"
# How often Windows checks for a key while waiting; it has no select() on the console.
WINDOWS_POLL_SECONDS = 0.05


def split_keys(text):
    """Split what one read returned into keys.

    Arrow and function keys arrive as an escape sequence such as "\\x1b[A"; that comes back as one
    item, so it can't be mistaken for Esc followed by typed text. A lone "\\x1b" is the Esc key.
    """
    if text.startswith(ESCAPE) and len(text) > 1:
        return [text]
    return list(text)


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
        if key in ("\x00", "\xe0"):  # arrow and function keys: a prefix and a code, both ignored
            msvcrt.getwch()
            continue
        keys.append(key)
    return keys
