"""Short effects that play on a price cell right after it changes, like a trading screen."""

from tgju_rates.ansi import BOLD

# "board" is roll and flash together, like an exchange's departure-style board.
ANIMATIONS = ("flash", "glow", "roll", "board", "off")
DEFAULT_ANIMATION = "flash"
ANIMATION_SECONDS = 1.5
# Live mode redraws this often while an animation plays; the screen only rewrites lines that changed.
FRAME_SECONDS = 1 / 15
# Digits settle one after another, left to right, within this share of the animation.
ROLL_SHARE = 0.6

# 256-colour ramps from the brightest step to the last one before the cell returns to normal.
FLASH_BACKGROUNDS = {"up": (34, 28, 22, 22), "down": (160, 124, 88, 52)}
GLOW_COLOURS = {"up": (231, 46, 46, 83, 114), "down": (231, 196, 196, 203, 203)}
FLASH_TEXT = "\033[38;5;231m"


def ramp_step(ramp, age):
    """The ramp entry for ``age`` seconds into the animation."""
    return ramp[min(int(age / ANIMATION_SECONDS * len(ramp)), len(ramp) - 1)]


def cell_style(animation, direction, age):
    """The style for a changed cell ``age`` seconds after the change, or None when nothing plays."""
    if age >= ANIMATION_SECONDS:
        return None
    if animation in ("flash", "board"):
        return f"{BOLD}{FLASH_TEXT}\033[48;5;{ramp_step(FLASH_BACKGROUNDS[direction], age)}m"
    if animation == "glow":
        return f"{BOLD}\033[38;5;{ramp_step(GLOW_COLOURS[direction], age)}m"
    return None


def uses_background(animation):
    """Whether the cell style sets a background that the row has to restore after the cell."""
    return animation in ("flash", "board")


def rolls(animation):
    return animation in ("roll", "board")


def rolled(old, new, age):
    """``new`` with its changed digits still spinning ``age`` seconds after the change.

    Both are right-aligned numbers like "3,014,200". Digits that differ from ``old`` spin, then settle
    one by one from the left, so the most significant change lands first. Commas and unchanged digits
    stay put, so the cell never changes width.
    """
    old = old.rjust(len(new))[-len(new) :]
    changed = [i for i, (o, n) in enumerate(zip(old, new)) if o != n and n.isdigit()]
    settle_span = ANIMATION_SECONDS * ROLL_SHARE
    tick = int(age / FRAME_SECONDS)
    chars = list(new)
    for order, index in enumerate(changed):
        if age < settle_span * (order + 1) / len(changed):
            # Spin away from the new digit, so a spinning cell never reads as already settled.
            chars[index] = str((int(new[index]) + 1 + (tick + order * 3) % 9) % 10)
    return "".join(chars)
