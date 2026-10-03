"""What the keyboard can change in live mode: unit, sort order, filter, converter, animation, pause."""

from tgju_rates.animation import ANIMATIONS, DEFAULT_ANIMATION
from tgju_rates.currencies import display_code, english_name, parse_change, parse_rial
from tgju_rates.keys import ESCAPE

SORT_MODES = ("site order", "biggest move", "price")
BACKSPACE = ("\x7f", "\b")
ENTER = ("\r", "\n")
KEY_HELP = "t toman/rial  s sort  / filter  c convert  a animation  p pause  q quit"


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

    def handle(self, key):
        # While a line is being typed, every key (q included) goes into it.
        if self.editing:
            self.filter, self.editing = edit_text(self.filter, key)
        elif self.converting:
            self.conversion, self.converting = edit_text(self.conversion, key)
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
        elif key == "p":
            self.paused = not self.paused
        elif key == "q":
            self.quit = True

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
