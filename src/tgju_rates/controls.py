"""What the keyboard can change in live mode: unit, sort order, filter, converter, animation, pause, and
the selected row with its detail view."""

from tgju_rates.animation import ANIMATIONS, DEFAULT_ANIMATION
from tgju_rates.currencies import display_code, english_name, parse_change, parse_rial
from tgju_rates.keys import DOWN_KEYS, ESCAPE, UP_KEYS

SORT_MODES = ("site order", "biggest move", "price")
BACKSPACE = ("\x7f", "\b")
ENTER = ("\r", "\n")
HELP_KEY = "?"
# The key bar at the bottom of the live screen: (key, what it does) for the current mode.
KEY_HINTS = (
    ("↑↓", "select"),
    ("Enter", "details"),
    ("t", "toman/rial"),
    ("s", "sort"),
    ("/", "filter"),
    ("c", "convert"),
    ("a", "animation"),
    ("m", "mute alerts"),
    ("p", "pause"),
    ("?", "help"),
    ("q", "quit"),
)
DETAIL_KEY_HINTS = (
    ("↑↓", "prev/next"),
    ("d", "1/7/30 days"),
    ("Esc", "back"),
    ("t", "toman/rial"),
    ("p", "pause"),
    ("?", "help"),
    ("q", "quit"),
)
TYPING_KEY_HINTS = (("Enter", "keep"), ("Esc", "clear"), ("Backspace", "delete"))
HELP_KEY_HINTS = (("Esc", "close"), ("q", "quit"))
# The ? overlay: every key, with a longer description than the key bar has room for.
HELP_LINES = (
    ("↑ ↓", "select a row, in the table or the dashboard"),
    ("Enter", "open the selected row: price, low/high, its alerts and a chart"),
    ("d", "in the details, show the last 1, 7 or 30 days"),
    ("t", "switch between toman and rial (alert limits keep their unit)"),
    ("s", "sort: site order, biggest move today, highest price"),
    ("/", "filter by code or name as you type; Enter keeps it, Esc clears it"),
    ("c", "convert, e.g. 250 usd eur; updates as you type and on every poll"),
    ("a", "next price animation: flash, glow, roll, board, off"),
    ("m", "mute alerts: no notifications, and the ALERT lines are cleared; m again unmutes"),
    ("p", "pause and resume updates"),
    ("Esc", "close the details; else clear the filter, converter and selection"),
    ("?", "show or hide this help"),
    ("q", "quit (Ctrl+C works too)"),
)
# How far back the detail view's chart goes; "d" cycles through these.
DETAIL_DAYS = (1, 7, 30)


def edit_text(text, key):
    """Apply one key to a line being typed. Returns (text, still typing); Enter keeps it, Esc clears it."""
    if key in ENTER:
        return text, False
    if key == ESCAPE:
        return "", False
    if key in BACKSPACE:
        return text[:-1], True
    if key.isprintable() and len(key) == 1:
        return text + key, True
    return text, True


def move_size(rate):
    parsed = parse_change(rate["change"])
    return abs(parsed[0]) if parsed else -1.0


def price_value(rate):
    price = parse_rial(rate["price"])
    return price if price is not None else -1


class LiveControls:
    """Holds the view state and changes it one key at a time."""

    def __init__(self, toman=False, animation=DEFAULT_ANIMATION):
        self.toman = toman
        self.animation = self.start_animation = animation
        self.sort = 0
        self.filter = ""
        self.editing = False
        # The converter line ("c"): what's typed, and whether it's still being typed.
        self.conversion = ""
        self.converting = False
        self.paused = False
        self.quit = False
        # The highlighted row's key (None until an arrow is pressed), and whether its detail view is open.
        self.selected = None
        self.detail = False
        self.detail_days = DETAIL_DAYS[0]
        # Whether alerts are muted ("m"): they're still checked, but neither notified nor listed.
        self.muted = False
        # Whether the ? overlay is open.
        self.help = False

    def handle(self, key, visible=()):
        """Apply one key. ``visible`` is the shown rows' keys in screen order, for the arrows and Enter."""
        # While a line is being typed, every key (q included) goes into it.
        if self.editing:
            self.filter, self.editing = edit_text(self.filter, key)
        elif self.converting:
            self.conversion, self.converting = edit_text(self.conversion, key)
        elif self.help:
            # The overlay covers the table, so only closing it and quitting do anything.
            if key in (HELP_KEY, ESCAPE):
                self.help = False
            elif key == "q":
                self.quit = True
        elif key == HELP_KEY:
            self.help = True
        elif key in UP_KEYS or key in DOWN_KEYS:
            self.move(visible, -1 if key in UP_KEYS else 1)
        elif key in ENTER:
            if self.selected not in visible:
                self.selected = visible[0] if visible else None
            self.detail = self.selected is not None
        elif self.detail and key == ESCAPE:
            self.detail = False
        elif self.detail and key == "d":
            self.detail_days = DETAIL_DAYS[(DETAIL_DAYS.index(self.detail_days) + 1) % len(DETAIL_DAYS)]
        elif self.detail and key in ("s", "/", "c"):
            pass  # the table they change isn't on screen
        elif key == "t":
            self.toman = not self.toman
        elif key == "s":
            self.sort = (self.sort + 1) % len(SORT_MODES)
        elif key == "a":
            self.animation = ANIMATIONS[(ANIMATIONS.index(self.animation) + 1) % len(ANIMATIONS)]
        elif key == "/":
            self.editing = True
        elif key == "c":
            self.converting = True
        elif key == ESCAPE:
            self.filter = self.conversion = ""
            self.selected = None
        elif key == "m":
            self.muted = not self.muted
        elif key == "p":
            self.paused = not self.paused
        elif key == "q":
            self.quit = True

    def hints(self):
        """The (key, action) pairs that apply right now, for the key bar."""
        if self.editing or self.converting:
            return TYPING_KEY_HINTS
        if self.help:
            return HELP_KEY_HINTS
        if self.detail:
            return DETAIL_KEY_HINTS
        if self.muted:
            return tuple((key, "unmute alerts") if key == "m" else (key, action) for key, action in KEY_HINTS)
        return KEY_HINTS

    def move(self, visible, step):
        """Select the next (``step`` 1) or previous (-1) visible row, starting from the top or bottom."""
        if not visible:
            return
        if self.selected not in visible:
            self.selected = visible[0] if step > 0 else visible[-1]
        else:
            self.selected = visible[max(0, min(len(visible) - 1, visible.index(self.selected) + step))]

    def apply(self, rates):
        """The rates to show: filtered by code or English name, then sorted."""
        needle = self.filter.strip().lower()
        if needle:
            rates = [
                rate
                for rate in rates
                if needle in display_code(rate["key"]).lower() or needle in english_name(rate["key"]).lower()
            ]
        mode = SORT_MODES[self.sort]
        if mode == "biggest move":
            return sorted(rates, key=move_size, reverse=True)
        if mode == "price":
            return sorted(rates, key=price_value, reverse=True)
        return list(rates)

    def describe(self):
        """A short summary of the non-default view settings, for the header."""
        parts = []
        if self.sort:
            parts.append(f"sorted by {SORT_MODES[self.sort]}")
        # Shown once changed, so cycling with "a" says which effect is now on.
        if self.animation != self.start_animation:
            parts.append(f"animation: {self.animation}")
        if self.editing:
            parts.append(f"filter: {self.filter}_  (Enter to keep, Esc to clear)")
        elif self.filter:
            parts.append(f"filter: {self.filter}  (Esc to clear)")
        return "   ".join(parts)
