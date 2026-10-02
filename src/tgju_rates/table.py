"""Rendering the rates as an aligned, optionally coloured text table."""

from tgju_rates.ansi import BOLD, DOWN, END_CELL, FLAT, HEADER_STYLE, RESET, STRIPE, UP
from tgju_rates.currencies import display_code, english_name, to_toman
from tgju_rates.tracking import TREND_POINTS

BASE_HEADER = ("CODE", "NAME", "PRICE (RIAL)", "TOMAN", "CHANGE", "LOW", "HIGH")
# One entry per base column above, so adding or reordering a column means updating all four.
COLUMN_STYLES = (
    f"{BOLD}\033[38;5;81m",  # code: cyan
    None,  # name: terminal's default text colour
    BOLD,  # price (rial): terminal's default text colour, bold
    "\033[38;5;179m",  # toman: muted gold
    None,  # change: green / red / grey by direction, see change_style()
    FLAT,  # low
    FLAT,  # high
)
COLUMN_ALIGNS = "<<>>>>>"
PRICE_COLUMN, CHANGE_COLUMN = 2, 4

SPARK_BLOCKS = "▁▂▃▄▅▆▇█"
COLUMN_GAP = "  "


def sparkline(prices):
    """Draw prices as block characters, scaled between their own low and high."""
    # A single price is just the starting point, not a trend yet.
    if len(prices) < 2:
        return ""
    low, high = min(prices), max(prices)
    if low == high:
        return SPARK_BLOCKS[0] * len(prices)
    top = len(SPARK_BLOCKS) - 1
    return "".join(SPARK_BLOCKS[round((price - low) / (high - low) * top)] for price in prices)


def trend_style(prices):
    if len(prices) < 2 or prices[-1] == prices[0]:
        return FLAT
    return UP if prices[-1] > prices[0] else DOWN


def change_style(change):
    """Colour a change like "(-0.5%) -100" by its direction."""
    percent = change.partition("%")[0].lstrip("(")
    try:
        value = float(percent)
    except ValueError:
        return FLAT
    return UP if value > 0 else DOWN if value < 0 else FLAT


def render_table(rates, *, color, persian=False, tracker=None, now=0.0):
    """Return the table as a string.

    With a ``tracker`` (live mode), recently moved prices get a ▲/▼ marker and a TREND column is
    added. With ``persian``, the Persian names go in a last column, so right-to-left text doesn't
    break the alignment of the columns before it.
    """
    header = list(BASE_HEADER)
    aligns = COLUMN_ALIGNS
    rows = [
        [
            display_code(rate["key"]),
            english_name(rate["key"]),
            rate["price"],
            to_toman(rate["price"]),
            rate["change"],
            rate["low"],
            rate["high"],
        ]
        for rate in rates
    ]
    if tracker is not None:
        header.append("TREND")
        aligns += "<"
        for row, rate in zip(rows, rates):
            # Fixed width, so the table doesn't shift as sparklines grow.
            row.append(sparkline(tracker.trends.get(rate["key"], ())).ljust(TREND_POINTS))
    if persian:
        header.append("PERSIAN")
        aligns += "<"
        for row, rate in zip(rows, rates):
            row.append(rate["name"])
    # Every cell is padded, including the last, so the stripe forms an even band.
    widths = [max(len(row[i]) for row in (header, *rows)) for i in range(len(header))]

    def line(row, styles=None):
        cells = [
            cell.ljust(width) if align == "<" else cell.rjust(width) for cell, width, align in zip(row, widths, aligns)
        ]
        if styles:
            cells = [f"{style}{cell}{END_CELL}" if style else cell for style, cell in zip(styles, cells)]
        return COLUMN_GAP.join(cells)

    header_styles = [HEADER_STYLE] * len(header) if color else None
    rule = "-" * (sum(widths) + len(COLUMN_GAP) * len(widths) + 1)
    lines = [("   " + line(header, header_styles)).rstrip(), rule]
    for index, (rate, row) in enumerate(zip(rates, rows)):
        styles = list(COLUMN_STYLES)
        if tracker is not None:
            styles.append(trend_style(tracker.trends.get(rate["key"], ())))
        if persian:
            styles.append(None)
        styles[CHANGE_COLUMN] = change_style(row[CHANGE_COLUMN])
        move = tracker.recent_move(rate["key"], now) if tracker is not None else None
        if move:
            arrow, tint = ("▲", UP) if move == "up" else ("▼", DOWN)
            # A fresh move recolours the price itself, so the eye lands on what changed.
            styles[PRICE_COLUMN] = f"{BOLD}{tint}"
            marker = f" {tint}{BOLD}{arrow}{END_CELL} " if color else f" {arrow} "
        else:
            marker = "   "
        if color:
            stripe = STRIPE if index % 2 else ""
            lines.append(f"{stripe}{marker}{line(row, styles)} {RESET}")
        else:
            lines.append((marker + line(row)).rstrip())
    return "\n".join(lines)
