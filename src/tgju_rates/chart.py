"""Terminal charts of saved prices, for ``--history CODE --chart``."""

from datetime import datetime

from tgju_rates.ansi import DOWN, FLAT, RESET, UP

CHART_HEIGHT = 12
# Eighths of a cell, so each row of the chart has eight steps of height.
PARTIAL_BLOCKS = " ▁▂▃▄▅▆▇█"
STEPS = len(PARTIAL_BLOCKS) - 1


def resample(points, start, end, columns):
    """The price in effect at the end of each of ``columns`` equal time slots; None before the first point.

    ``points`` are (time, price) pairs, oldest first. Prices are steps: each holds until the next change.
    """
    values, index, current = [], 0, None
    for column in range(columns):
        slot_end = start + (end - start) * (column + 1) / columns
        while index < len(points) and points[index][0] <= slot_end:
            current = points[index][1]
            index += 1
        values.append(current)
    return values


def direction_style(first, last):
    return FLAT if first == last else UP if last > first else DOWN


def render_chart(values, start, end, *, height=CHART_HEIGHT, color=False):
    """A filled chart of ``values`` (one per column, None for no data), with price labels and the time span."""
    known = [value for value in values if value is not None]
    low, high = min(known), max(known)
    levels = height * STEPS

    def level(value):
        # A flat line sits mid-height; otherwise the low is one step and the high fills the top.
        if high == low:
            return levels // 2
        return 1 + round((value - low) / (high - low) * (levels - 1))

    filled = [None if value is None else level(value) for value in values]
    labels = {0: f"{high:,}", height - 1: f"{low:,}"}
    if height > 2:
        labels[height // 2] = f"{(high + low) // 2:,}"
    label_width = max(len(label) for label in labels.values())
    style, end_style = (direction_style(known[0], known[-1]), RESET) if color else ("", "")

    lines = []
    for row in range(height):
        floor = (height - 1 - row) * STEPS
        cells = "".join(" " if steps is None else PARTIAL_BLOCKS[max(0, min(STEPS, steps - floor))] for steps in filled)
        axis = "┤" if row in labels else "│"
        lines.append(f"{labels.get(row, ''):>{label_width}} {axis}{style}{cells}{end_style}".rstrip())
    lines.append(f"{'':>{label_width}} └{'─' * len(values)}")
    time_format = "%H:%M" if end - start <= 86400 else "%Y-%m-%d %H:%M"
    left, right = (datetime.fromtimestamp(stamp).strftime(time_format) for stamp in (start, end))
    gap = max(1, len(values) - len(left) - len(right))
    lines.append(f"{'':>{label_width}}  {left}{' ' * gap}{right}")
    return "\n".join(lines)


def daily_rows(points):
    """(date, open, low, high, close) for each local day that has a saved price, oldest first."""
    days = {}
    for stamp, price in points:
        days.setdefault(datetime.fromtimestamp(stamp).date(), []).append(price)
    return [(day, prices[0], min(prices), max(prices), prices[-1]) for day, prices in days.items()]


def daily_summary(points, *, color=False):
    """One line per day: open, low, high, close, and the close's change from the day before."""
    header = ("DATE", "OPEN", "LOW", "HIGH", "CLOSE", "CHANGE")
    rows, styles, previous = [], [], None
    for day, opened, low, high, close in daily_rows(points):
        change = ""
        if previous is not None:
            percent = (close - previous) / previous * 100 if previous else 0.0
            change = f"{close - previous:+,} ({percent:+.1f}%)"
        styles.append(direction_style(previous, close) if previous is not None else "")
        rows.append([day.isoformat(), f"{opened:,}", f"{low:,}", f"{high:,}", f"{close:,}", change])
        previous = close
    widths = [max(len(row[i]) for row in (header, *rows)) for i in range(len(header))]

    def line(cells):
        return "  ".join(
            [cells[0].ljust(widths[0])] + [cell.rjust(width) for cell, width in zip(cells[1:], widths[1:])]
        )

    lines = [line(header)]
    for row, style in zip(rows, styles):
        text = line(row)
        if color and style and row[-1]:
            text = text[: -len(row[-1])] + f"{style}{row[-1]}{RESET}"
        lines.append(text.rstrip())
    return "\n".join(lines)
