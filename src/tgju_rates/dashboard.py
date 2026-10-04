"""The dashboard: currencies, gold coins, gold and crypto as panels side by side on one screen."""

from tgju_rates.animation import ANIMATION_SECONDS, cell_style, rolled, rolls, uses_background
from tgju_rates.ansi import BOLD, DEFAULT_BACKGROUND, DOWN, END_CELL, HEADER_STYLE, RESET, UP
from tgju_rates.currencies import UNIT_NAMES, display_code, parse_change, rial_to_toman, to_toman
from tgju_rates.markets import market_of
from tgju_rates.table import (
    COLUMN_GAP,
    COLUMN_STYLES,
    MARKER_WIDTH,
    change_style,
    row_background,
    sparkline,
    trend_style,
)
from tgju_rates.tracking import TREND_POINTS

# What the dashboard shows without --watch, in this order; panels follow the order of their first code.
DASHBOARD_CODES = (
    *("usd", "eur", "gbp", "aed", "try", "cny"),
    *("emami", "bahar", "nim", "rob", "gerami"),
    *("gold18", "gold24", "mesghal", "silver"),
    *("btc", "eth", "usdt", "bnb", "sol", "xrp"),
)
PANEL_TITLES = {"currency": "CURRENCIES", "coin": "GOLD COINS", "gold": "GOLD & SILVER", "crypto": "CRYPTO"}
PANEL_GAP = "    "


def group_by_market(rates):
    """[(market, rates)] in the order each market first appears, keeping the rates' order within it."""
    groups = {}
    for rate in rates:
        groups.setdefault(market_of(rate["key"]), []).append(rate)
    return list(groups.items())


def percent_text(change):
    """Just the percent of a change cell, e.g. "+0.32%"; "-" when it can't be read."""
    parsed = parse_change(change)
    return f"{parsed[0]:+.2f}%" if parsed else "-"


def render_panel(market, rates, *, color, toman=False, tracker=None, now=0.0, animation="off", selected=None):
    """One market's panel as (lines, width); every line is padded to ``width`` visible columns."""
    header = ["CODE", f"PRICE ({UNIT_NAMES[toman].upper()})", "CHANGE"]
    aligns = "<>>"
    rows = [
        [display_code(rate["key"]), to_toman(rate["price"]) if toman else rate["price"], percent_text(rate["change"])]
        for rate in rates
    ]
    if tracker is not None:
        header.append("TREND")
        aligns += "<"
        for row, rate in zip(rows, rates):
            row.append(sparkline(tracker.trends.get(rate["key"], ())).ljust(TREND_POINTS))
    widths = [max(len(row[i]) for row in (header, *rows)) for i in range(len(header))]
    width = MARKER_WIDTH + sum(widths) + len(COLUMN_GAP) * (len(widths) - 1)

    def cells(row):
        return [cell.ljust(w) if align == "<" else cell.rjust(w) for cell, w, align in zip(row, widths, aligns)]

    def styled(padded, styles, ends):
        parts = zip(padded, styles, ends)
        return COLUMN_GAP.join(f"{style}{cell}{end}" if style else cell for cell, style, end in parts)

    title = f"{PANEL_TITLES.get(market, market.upper())} "
    title = title + "─" * (width - len(title))
    head = " " * MARKER_WIDTH + COLUMN_GAP.join(cells(header))
    if color:
        title = f"{BOLD}{title}{RESET}"
        head = " " * MARKER_WIDTH + styled(cells(header), [HEADER_STYLE] * len(header), [END_CELL] * len(header))
    lines = [title, head]
    for index, (rate, row) in enumerate(zip(rates, rows)):
        move = tracker.recent_move(rate["key"], now) if tracker is not None else None
        arrow, tint = ("▲", UP) if move == "up" else ("▼", DOWN) if move else (" ", None)
        if not color:
            lines.append(f" {arrow} " + COLUMN_GAP.join(cells(row)))
            continue
        background = row_background(index, rate["key"], selected)
        styles = [COLUMN_STYLES[0], f"{BOLD}{tint}" if tint else BOLD, change_style(rate["change"])]
        if tracker is not None:
            styles.append(trend_style(tracker.trends.get(rate["key"], ())))
        ends = [END_CELL] * len(row)
        playing = tracker.recent_change(rate["key"], now, ANIMATION_SECONDS) if tracker is not None else None
        if playing and animation != "off":
            direction, old, age = playing
            if rolls(animation):
                row[1] = rolled(f"{rial_to_toman(old) if toman else old:,}", row[1], age)
            styles[1] = cell_style(animation, direction, age) or styles[1]
            if uses_background(animation):
                ends[1] = END_CELL + (background or DEFAULT_BACKGROUND)
        marker = f" {tint}{BOLD}{arrow}{END_CELL} " if tint else "   "
        lines.append(f"{background}{marker}{styled(cells(row), styles, ends)}{RESET}")
    return lines, width


def arrange(panels, width):
    """Split panels into rows that fit ``width``, as evenly as possible (four panels go 2+2, not 3+1).

    Returns (rows, column widths); a grid column is as wide as its widest panel, so panels line up.
    """
    count = len(panels)
    for most in range(count, 0, -1):
        per_row = -(-count // -(-count // most))
        rows = [panels[i : i + per_row] for i in range(0, count, per_row)]
        columns = [max(row[i][1] for row in rows if i < len(row)) for i in range(per_row)]
        if per_row == 1 or sum(columns) + len(PANEL_GAP) * (per_row - 1) <= width:
            return rows, columns
    return [], []


def render_dashboard(rates, *, color, toman=False, tracker=None, now=0.0, animation="off", width=80, selected=None):
    """The rates as one panel per market, laid out in a grid as wide as ``width`` allows."""
    panels = [
        render_panel(
            market, group, color=color, toman=toman, tracker=tracker, now=now, animation=animation, selected=selected
        )
        for market, group in group_by_market(rates)
    ]
    rows, columns = arrange(panels, width)
    blocks = []
    for row in rows:
        height = max(len(lines) for lines, _ in row)
        padded = [
            [line + " " * (column - own) for line in lines] + [" " * column] * (height - len(lines))
            for (lines, own), column in zip(row, columns)
        ]
        blocks.append("\n".join(PANEL_GAP.join(parts).rstrip() for parts in zip(*padded)))
    return "\n\n".join(blocks)
