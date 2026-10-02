"""ANSI escape sequences and the colour palette shared by the table and the live screen."""

DIM, BOLD, RESET = "\033[2m", "\033[1m", "\033[0m"
ALERT_STYLE = f"{BOLD}\033[38;5;214m"  # orange
CLEAR_SCREEN = "\033[H\033[2J"
CLEAR_LINE_END, CLEAR_BELOW = "\033[K", "\033[J"
# Live mode draws on the alternate screen with the cursor hidden and line wrap off, so a
# too-wide row is clipped instead of wrapping and pushing every later row out of place.
ENTER_LIVE_SCREEN = "\033[?1049h\033[?25l\033[?7l"
LEAVE_LIVE_SCREEN = "\033[?7h\033[?25h\033[?1049l"
# Dark grey background behind every other row, for easier reading across wide rows.
STRIPE = "\033[48;5;236m"
# Ends a cell's colour without clearing the row's stripe background.
END_CELL = "\033[22;39m"

# 256-colour palette: identifiers stand out, the price is brightest, secondary figures recede.
UP, DOWN, FLAT = "\033[38;5;114m", "\033[38;5;203m", "\033[38;5;244m"
HEADER_STYLE = f"{BOLD}\033[38;5;250m"


def move_to(row):
    """Move the cursor to the start of a 1-based screen row."""
    return f"\033[{row};1H"
