"""Rendering the rates as an aligned, optionally coloured text table."""

from tgju_rates.animation import ANIMATION_SECONDS, cell_style, rolled, rolls, uses_background
from tgju_rates.ansi import BOLD, DEFAULT_BACKGROUND, DOWN, END_CELL, FLAT, HEADER_STYLE, RESET, SELECTED, STRIPE, UP
from tgju_rates.currencies import display_code, english_name, format_change, parse_change, rial_to_toman, to_toman
from tgju_rates.tracking import TREND_POINTS

BASE_HEADER = ("CODE", "NAME", "PRICE (RIAL)", "TOMAN", "CHANGE", "LOW", "HIGH")
# With --toman, toman leads and rial becomes the secondary column.
TOMAN_HEADER = ("CODE", "NAME", "PRICE (TOMAN)", "RIAL", "CHANGE", "LOW", "HIGH")
# One entry per base column above, so adding or reordering a column means updating all four.
COLUMN_STYLES = (
    f"{BOLD}\033[38;5;81m",  # code: cyan
    None,  # name: terminal's default text colour
    BOLD,  # price (rial): terminal's default text colour, bold
    "\033[38;5;179m",  # secondary unit (toman, or rial with --toman): muted gold
    None,  # change: green / red / grey by direction, see change_style()
    FLAT,  # low
    FLAT,  # high
)
COLUMN_ALIGNS = "<<>>>>>"
PRICE_COLUMN, SECONDARY_COLUMN, CHANGE_COLUMN = 2, 3, 4

# The ▲/▼ marker before each row is fixed width.
MARKER_WIDTH = 3

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
    """Colour a change cell like "(-0.5%) -100" (as the site gives it) by its direction."""
    parsed = parse_change(change)
    value = parsed[0] if parsed else 0
    return UP if value > 0 else DOWN if value < 0 else FLAT


def base_row(rate, toman):
    code, name = display_code(rate["key"]), english_name(rate["key"])
    change = format_change(rate["change"], toman)
    if not toman:
        return [code, name, rate["price"], to_toman(rate["price"]), change, rate["low"], rate["high"]]
    return [
        code,
        name,
        to_toman(rate["price"]),
        rate["price"],
        change,
        to_toman(rate["low"]),
        to_toman(rate["high"]),
    ]


def price_texts(rial, toman):
    """The price and secondary-unit cells for a rial amount, in the order the table shows them."""
    texts = [f"{rial:,}", f"{rial_to_toman(rial):,}"]
    return texts[::-1] if toman else texts


def row_background(index, key, selected):
    """The background a row is drawn on: the selection's, the stripe on every other row, or "" for none."""
    if key == selected:
        return SELECTED
    return STRIPE if index % 2 else ""


def render_table(rates, *, color, persian=False, toman=False, tracker=None, now=0.0, animation="off", selected=None):
    """Return the table as a string.

    With ``toman``, prices, change, low and high are in toman and the rial price is the second column.

    With a ``tracker`` (live mode), recently moved prices get a ▲/▼ marker and a TREND column is
    added. With ``color`` too, the price cells of a fresh move play ``animation`` (see animation.py).

    With ``persian``, the Persian names go in a last column, so right-to-left text doesn't break the
    alignment of the columns before it.

    ``selected`` is the key of a row to highlight (only with ``color``).
    """
    header = list(TOMAN_HEADER if toman else BASE_HEADER)
    aligns = COLUMN_ALIGNS
    rows = [base_row(rate, toman) for rate in rates]
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

    def line(row, styles=None, ends=None):
        cells = [
            cell.ljust(width) if align == "<" else cell.rjust(width) for cell, width, align in zip(row, widths, aligns)
        ]
        if styles:
            ends = ends or [END_CELL] * len(cells)
            cells = [f"{style}{cell}{end}" if style else cell for style, cell, end in zip(styles, cells, ends)]
        return COLUMN_GAP.join(cells)

    header_styles = [HEADER_STYLE] * len(header) if color else None
    rule = "-" * (sum(widths) + len(COLUMN_GAP) * len(widths) + MARKER_WIDTH - 2)
    lines = [(" " * MARKER_WIDTH + line(header, header_styles)).rstrip(), rule]
    for index, (rate, row) in enumerate(zip(rates, rows)):
        styles = list(COLUMN_STYLES)
        if tracker is not None:
            styles.append(trend_style(tracker.trends.get(rate["key"], ())))
        if persian:
            styles.append(None)
        styles[CHANGE_COLUMN] = change_style(rate["change"])
        move = tracker.recent_move(rate["key"], now) if tracker is not None else None
        if move:
            arrow, tint = ("▲", UP) if move == "up" else ("▼", DOWN)
            # A fresh move recolours the price itself, so the eye lands on what changed.
            styles[PRICE_COLUMN] = f"{BOLD}{tint}"
            marker = f" {tint}{BOLD}{arrow}{END_CELL} " if color else f" {arrow} "
        else:
            marker = "   "
        ends = [END_CELL] * len(row)
        background = row_background(index, rate["key"], selected)
        playing = tracker.recent_change(rate["key"], now, ANIMATION_SECONDS) if color and tracker else None
        if playing and animation != "off":
            direction, old, age = playing
            for column, old_text in zip((PRICE_COLUMN, SECONDARY_COLUMN), price_texts(old, toman)):
                if rolls(animation):
                    row[column] = rolled(old_text, row[column], age)
                styles[column] = cell_style(animation, direction, age) or styles[column]
                if uses_background(animation):
                    # Hand the background back to the row, or the flash would run on into the next cells.
                    ends[column] = END_CELL + (background or DEFAULT_BACKGROUND)
        if color:
            lines.append(f"{background}{marker}{line(row, styles, ends)} {RESET}")
        else:
            lines.append((marker + line(row)).rstrip())
    return "\n".join(lines)


HOLDINGS_HEADER = ("YOUR SAVINGS", "AMOUNT", "WORTH", "SINCE BOUGHT", "TODAY")
HOLDINGS_ALIGNS = "<>>>>"


def format_count(amount):
    return f"{int(amount):,}" if amount == int(amount) else f"{amount:,.4f}".rstrip("0")


def percent_cell(value):
    """A percentage with its direction, e.g. "▲ +32.2%"; "" when unknown."""
    if value is None:
        return ""
    arrow = "▲ " if value > 0 else "▼ " if value < 0 else "  "
    return f"{arrow}{value:+.1f}%"


def percent_style(value):
    return FLAT if not value else UP if value > 0 else DOWN


def render_holdings(valuation, *, color, toman=False, trend=()):
    """The savings panel: what each holding is worth now, its gain since bought, and today's move."""
    unit = "TOMAN" if toman else "RIAL"

    def amount(rial):
        if rial is None:
            return "-"
        return f"{rial_to_toman(rial) if toman else rial:,}"

    header = list(HOLDINGS_HEADER)
    header[2] = f"WORTH ({unit})"
    rows = [
        (
            [
                display_code(position.holding.key),
                format_count(position.holding.amount),
                amount(position.worth),
                percent_cell(position.gain_percent),
                percent_cell(position.today_percent),
            ],
            (position.gain_percent, position.today_percent),
        )
        for position in valuation.positions
    ]
    total = [
        "TOTAL",
        "",
        amount(valuation.worth),
        percent_cell(valuation.gain_percent),
        percent_cell(valuation.today_percent),
    ]
    rows.append((total, (valuation.gain_percent, valuation.today_percent)))
    widths = [max(len(row[i]) for row in (header, *(cells for cells, _ in rows))) for i in range(len(header))]

    def line(cells, styles):
        padded = [
            cell.ljust(width) if align == "<" else cell.rjust(width)
            for cell, width, align in zip(cells, widths, HOLDINGS_ALIGNS)
        ]
        if color:
            padded = [f"{style}{cell}{END_CELL}" if style else cell for style, cell in zip(styles, padded)]
        return " " * MARKER_WIDTH + COLUMN_GAP.join(padded)

    lines = [line(header, [HEADER_STYLE] * len(header))]
    for index, (cells, (gain, today)) in enumerate(rows):
        is_total = index == len(rows) - 1
        code_style = f"{BOLD}" if is_total else COLUMN_STYLES[0]
        worth_style = BOLD if is_total else None
        text = line(cells, [code_style, FLAT, worth_style, percent_style(gain), percent_style(today)])
        if is_total and len(trend) >= 2:
            spark = sparkline(list(trend))
            text += COLUMN_GAP + (f"{trend_style(list(trend))}{spark}{END_CELL}" if color else spark)
        lines.append(text.rstrip())
    return "\n".join(lines)
