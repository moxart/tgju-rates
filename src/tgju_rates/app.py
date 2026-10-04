"""The run modes: print the table once, poll the feed and keep the table live, or show saved history."""

import csv
import io
import shutil
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime

from tgju_rates.alerts import check_alerts, notify
from tgju_rates.animation import ANIMATION_SECONDS, DEFAULT_ANIMATION, FRAME_SECONDS
from tgju_rates.ansi import ALERT_STYLE, BOLD, DIM, DOWN, END_CELL, RESET, UP
from tgju_rates.chart import CHART_HEIGHT, daily_summary, render_chart, resample
from tgju_rates.controls import DETAIL_KEY_HELP, KEY_HELP, LiveControls
from tgju_rates.convert import quick_conversion
from tgju_rates.currencies import (
    ENGLISH_NAMES,
    UNIT_NAMES,
    change_in_toman,
    display_code,
    english_name,
    parse_rial,
    rial_to_toman,
    to_toman,
)
from tgju_rates.dashboard import group_by_market, render_dashboard
from tgju_rates.dates import format_stamp
from tgju_rates.export import history_json, rates_json
from tgju_rates.holdings import TotalTrend, value_holdings
from tgju_rates.keys import KeyReader
from tgju_rates.markets import INSTRUMENTS, market_of
from tgju_rates.screen import LiveScreen, print_frame
from tgju_rates.source import SITE_NAME, apply_live_prices, fetch_live_prices
from tgju_rates.table import change_style, render_holdings, render_table, sparkline
from tgju_rates.tracking import HIGHLIGHT_SECONDS, TREND_POINTS, PriceTracker

# How many fired alerts stay listed above the live table.
RECENT_ALERTS_SHOWN = 5
# How many days the detail view lists under its chart.
DETAIL_SUMMARY_DAYS = 7
# After a failed poll the wait doubles each time, up to this many seconds (or the interval, if longer).
MAX_RETRY_SECONDS = 120


@dataclass(frozen=True)
class Options:
    persian: bool = False
    toman: bool = False
    json: bool = False
    animation: str = DEFAULT_ANIMATION
    dashboard: bool = False
    jalali: bool = False


def terminal_width():
    return shutil.get_terminal_size().columns


def run_once(rates, shown, alerts, options, history=None, holdings=()):
    now = time.time()
    if history is not None:
        record_history(history, rates, now)
    valuation = value_holdings(holdings, rates) if holdings else None
    fired = check_alerts(alerts, rates, set(), options.toman, total=valuation.complete_worth if valuation else None)
    if options.json:
        print(rates_json(shown, now=now, toman=options.toman, alerts=fired, valuation=valuation))
        return
    color = sys.stdout.isatty()
    print(f"Source: {SITE_NAME}   ({len(shown)} rates)\n")
    if valuation:
        print(render_holdings(valuation, color=color, toman=options.toman) + "\n")
    if options.dashboard:
        print(render_dashboard(shown, color=color, toman=options.toman, width=terminal_width()))
    else:
        print(render_table(shown, color=color, persian=options.persian, toman=options.toman))
    if fired:
        start, end = (ALERT_STYLE, RESET) if color else ("", "")
        print("\n" + "\n".join(f"{start}ALERT{end}  {message}" for message in fired))


def run_live(rates, shown, alerts, interval, options, history=None, holdings=(), notice=""):
    """Poll forever. ``rates`` is every currency (alerts can watch any); ``shown`` is what's displayed.

    ``notice`` is a line shown above the table, e.g. that the list came from saved history.
    """
    settings = dict(history=history, holdings=holdings, notice=notice)
    if options.json:
        session = LiveSession(rates, shown, alerts, interval, options, color=False, **settings)
        session.run(lambda frame: print(frame, flush=True))
    elif not sys.stdout.isatty():
        session = LiveSession(rates, shown, alerts, interval, options, color=False, **settings)
        session.run(lambda frame: print_frame(frame.split("\n")))
    else:
        session = LiveSession(rates, shown, alerts, interval, options, color=True, **settings)
        with LiveScreen() as screen:

            def draw(frame):
                screen.draw(frame.split("\n"))

            if sys.stdin.isatty():
                with KeyReader() as keys:
                    session.run(draw, keys)
            else:
                session.run(draw)


def record_history(history, rates, now):
    """Save changed prices; returns an error message instead of raising, so a full disk doesn't stop polling."""
    try:
        history.record(rates, now)
    except sqlite3.Error as error:
        return f"history not saved: {error}"
    return None


def saved_rates(history, markets):
    """Rows rebuilt from the last saved price of every key in ``markets``, for when tgju.org can't be reached.

    Change, low and high aren't saved, so they show "-" until the feed fills them in.
    """
    latest = history.latest()
    order = {key: index for index, key in enumerate(ENGLISH_NAMES)}
    keys = sorted(
        (key for key in latest if market_of(key) in markets), key=lambda key: (order.get(key, len(order)), key)
    )
    return [
        {
            "key": key,
            "name": INSTRUMENTS[key].persian if key in INSTRUMENTS else "",
            "price": f"{latest[key][1]:,}",
            "change": "-",
            "low": "-",
            "high": "-",
            "time": datetime.fromtimestamp(latest[key][0]).strftime("%Y-%m-%d %H:%M"),
        }
        for key in keys
    ]


class LiveSession:
    def __init__(self, rates, shown, alerts, interval, options, color, history=None, holdings=(), notice=""):
        self.rates, self.shown, self.alerts = rates, shown, alerts
        self.interval, self.options, self.color = interval, options, color
        self.notice = notice
        self.history = history
        self.holdings = holdings
        self.valuation = None
        self.total_trend = TotalTrend(TREND_POINTS)
        self.tracker = PriceTracker()
        if history is not None:
            self.tracker.load_trends({rate["key"]: history.recent_prices(rate["key"], TREND_POINTS) for rate in rates})
            if holdings:
                self.total_trend.seed(history, holdings, time.time())
        self.tracker.update(rates, time.time())
        self.active_alerts = set()
        self.fired_alerts = []
        self.recent_alerts = []
        self.status = "connected"
        # Polls that failed in a row; each one doubles the wait before the next (see poll_delay).
        self.failures = 0
        self.updated_at = time.time()
        self.controls = LiveControls(toman=options.toman, animation=options.animation)
        self.interactive = False
        # Whether the last frame drawn was mid-animation, so the loop keeps drawing until it settles.
        self.animating = False

    def run(self, draw, keys=None):
        """Poll every interval and redraw. With ``keys``, key presses redraw at once; ``q`` returns.

        While a price animation plays, frames are drawn every FRAME_SECONDS in between.
        """
        self.interactive = keys is not None
        next_poll = 0.0
        while True:
            if not self.controls.paused and time.time() >= next_poll:
                self.poll()
                next_poll = time.time() + self.poll_delay()
                draw(self.frame(time.time()))
            elif self.animating:
                draw(self.frame(time.time()))
            # While paused there's nothing to wait for but a key.
            wait = None if self.controls.paused else max(0.0, next_poll - time.time())
            if self.animating:
                wait = FRAME_SECONDS if wait is None else min(wait, FRAME_SECONDS)
            if keys is None:
                time.sleep(wait)
                continue
            pressed = keys.read(wait)
            for key in pressed:
                self.controls.handle(key, self.visible_keys())
            if self.controls.quit:
                return
            if pressed:
                draw(self.frame(time.time()))

    def poll_delay(self):
        """Seconds until the next poll: the interval, doubled for each failure in a row, up to a cap."""
        if not self.failures:
            return self.interval
        return min(self.interval * 2**self.failures, max(self.interval, MAX_RETRY_SECONDS))

    def poll(self):
        now = self.updated_at = time.time()
        try:
            apply_live_prices(self.rates, fetch_live_prices())
            self.status = "connected"
            self.failures = 0
        except (OSError, ValueError, KeyError) as error:
            self.failures += 1
            self.status = f"feed error, retrying in {self.poll_delay():g}s: {error}"
        self.tracker.update(self.rates, now)
        if self.history is not None:
            history_error = record_history(self.history, self.rates, now)
            if history_error:
                self.status += f"; {history_error}"
        if self.holdings:
            self.valuation = value_holdings(self.holdings, self.rates)
            self.total_trend.add(self.valuation.complete_worth)
        total = self.valuation.complete_worth if self.valuation else None
        stamp = datetime.fromtimestamp(now).strftime("%H:%M:%S")
        self.fired_alerts = check_alerts(self.alerts, self.rates, self.active_alerts, self.controls.toman, total=total)
        for message in self.fired_alerts:
            notify(message)
            self.recent_alerts.append(f"{stamp}  {message}")
        del self.recent_alerts[:-RECENT_ALERTS_SHOWN]

    def visible_keys(self):
        """The shown rows' keys in screen order, which the arrow keys step through."""
        shown = self.controls.apply(self.shown)
        if self.options.dashboard:
            shown = [rate for _, group in group_by_market(shown) for rate in group]
        return [rate["key"] for rate in shown]

    def detail_rate(self):
        """The rate whose detail view is open, or None."""
        if not self.controls.detail:
            return None
        return next((rate for rate in self.rates if rate["key"] == self.controls.selected), None)

    def is_animating(self, now):
        # The detail view has no animated cells, and redrawing it would re-read the history file.
        if not self.color or self.controls.animation == "off" or self.detail_rate():
            return False
        return any(self.tracker.recent_change(rate["key"], now, ANIMATION_SECONDS) for rate in self.shown)

    def frame(self, now):
        self.animating = self.is_animating(now)
        if self.options.json:
            return rates_json(
                self.shown, now=now, toman=self.controls.toman, alerts=self.fired_alerts, valuation=self.valuation
            )
        dim_start, dim_end = (DIM, RESET) if self.color else ("", "")
        alert_start, alert_end = (ALERT_STYLE, RESET) if self.color else ("", "")
        if self.options.jalali:
            stamp = format_stamp(self.updated_at, jalali=True, seconds=True)
        else:
            stamp = datetime.fromtimestamp(self.updated_at).strftime("%H:%M:%S")
        watching = f"{dim_start}Watching {len(self.alerts)} alert(s).{dim_end}\n" if self.alerts else ""
        notice = f"{alert_start}NOTE{alert_end} {self.notice}\n" if self.notice else ""
        alert_lines = "".join(f"{alert_start}ALERT{alert_end} {line}\n" for line in self.recent_alerts)
        shown = self.controls.apply(self.shown)
        controls = self.controls
        view_settings = dict(
            color=self.color,
            toman=controls.toman,
            tracker=self.tracker,
            now=now,
            animation=controls.animation,
            selected=controls.selected,
        )
        if self.options.dashboard:
            table = render_dashboard(shown, width=terminal_width(), **view_settings)
        else:
            table = render_table(shown, persian=self.options.persian, **view_settings)
        savings = ""
        if self.valuation:
            trend = self.total_trend.values
            savings = render_holdings(self.valuation, color=self.color, toman=self.controls.toman, trend=trend)
            savings += "\n\n"
        state = "PAUSED" if self.controls.paused else f"every {self.interval:g}s"
        view = self.controls.describe()
        view_line = f"{view}\n" if view else ""
        convert_line = self.convert_line(dim_start, dim_end)
        detail = self.detail_rate()
        help_text = DETAIL_KEY_HELP if detail else KEY_HELP
        key_help = f"{dim_start}Keys: {help_text}{dim_end}\n" if self.interactive else ""
        quit_hint = "" if self.interactive else "  Ctrl+C to quit."
        empty = "\nNo currency matches the filter." if self.controls.filter and not shown else ""
        body = self.detail_view(detail, now) if detail else f"{savings}{table}{empty}"
        return (
            f"tgju.org live rates   updated {stamp}   {state}   {self.status}\n"
            f"{dim_start}▲/▼ marks prices that moved in the last {HIGHLIGHT_SECONDS}s.  "
            f"TREND shows the last {TREND_POINTS} price changes.{quit_hint}{dim_end}\n"
            f"{key_help}"
            f"{notice}{view_line}{convert_line}{watching}{alert_lines}\n"
            f"{body}"
        )

    def detail_view(self, rate, now):
        """One rate in full: price, change, low/high, its alerts, and a chart of its saved prices."""
        key, toman, color = rate["key"], self.controls.toman, self.color
        bold, end = (BOLD, RESET) if color else ("", "")

        def amount(text):
            return to_toman(text) if toman else text

        title = f"{bold}{display_code(key)}  {english_name(key)}{end}"
        if self.options.persian and rate["name"]:
            title += f"   {rate['name']}"
        change = change_in_toman(rate["change"]) if toman else rate["change"]
        if color:
            change = f"{change_style(rate['change'])}{change}{END_CELL}"
        lines = [
            title,
            f"price {bold}{amount(rate['price'])}{end} {UNIT_NAMES[toman]}   change {change}   "
            f"low {amount(rate['low'])}   high {amount(rate['high'])}",
        ]
        rules = [alert.describe(toman) for alert in self.alerts if alert.key == key]
        if rules:
            lines.append("alerts: " + ", ".join(rules))
        lines.append("")
        if self.history is None:
            lines.append("History is off (--no-record), so there's no chart.")
            return "\n".join(lines)
        days = self.controls.detail_days
        start = now - days * 86400
        try:
            points = chart_points(self.history, key, start, self.history.changes_since(key, start))
        except sqlite3.Error as error:
            lines.append(f"Could not read the history file: {error}")
            return "\n".join(lines)
        chart = format_chart(
            key,
            days,
            points,
            start,
            now,
            toman=toman,
            color=color,
            width=terminal_width(),
            jalali=self.options.jalali,
            last_days=DETAIL_SUMMARY_DAYS,
        )
        lines.append(chart)
        return "\n".join(lines)

    def convert_line(self, dim_start, dim_end):
        """The converter's line ("c"), worked out from the latest polled prices of every loaded rate."""
        controls = self.controls
        if not controls.converting and not controls.conversion:
            return ""
        prices = {rate["key"]: parse_rial(rate["price"]) for rate in self.rates}
        result = quick_conversion(controls.conversion, {key: price for key, price in prices.items() if price})
        cursor, hint = ("_", "Enter to keep, Esc to close") if controls.converting else ("", "c to edit, Esc to close")
        return f"convert: {controls.conversion}{cursor}  →  {result}   {dim_start}({hint}){dim_end}\n"


HISTORY_VIEWS = ("list", "chart", "csv")


def run_history(history, key, days, options, now=None, view="list"):
    """Print saved prices of one currency: as a list, a chart with a daily summary, CSV, or JSON."""
    now = time.time() if now is None else now
    start = now - days * 86400
    changes = history.changes_since(key, start)
    color, jalali = sys.stdout.isatty(), options.jalali
    if options.json:
        print(history_json(key, changes, toman=options.toman))
    elif view == "csv":
        print(history_csv(key, changes, toman=options.toman, jalali=jalali), end="")
    elif view == "chart":
        points = chart_points(history, key, start, changes)
        width = terminal_width()
        print(format_chart(key, days, points, start, now, toman=options.toman, color=color, width=width, jalali=jalali))
    else:
        print(format_history(key, days, changes, toman=options.toman, color=color, jalali=jalali))


def chart_points(history, key, start, changes):
    """``changes`` led by the price in effect when the window opens, so the chart doesn't start blank."""
    before = history.last_before(key, start)
    return ([(start, before[1])] if before else []) + changes


def history_csv(key, changes, *, toman=False, jalali=False):
    """CSV with ISO times; ``jalali`` adds a jalali_time column after it, for reading in a spreadsheet."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["time", *(["jalali_time"] if jalali else []), "code", f"price_{UNIT_NAMES[toman]}"])
    for stamp, price in changes:
        local = datetime.fromtimestamp(stamp).astimezone().isoformat(timespec="seconds")
        extra = [format_stamp(stamp, jalali=True, seconds=True)] if jalali else []
        writer.writerow([local, *extra, display_code(key), rial_to_toman(price) if toman else price])
    return out.getvalue()


def history_title(key, days, toman):
    return f"{display_code(key)} ({english_name(key)}), last {days:g} day(s), in {UNIT_NAMES[toman]}"


NO_HISTORY = "No saved prices. History is recorded while tgju-rates runs."


def format_chart(key, days, points, start, end, *, toman=False, color=False, width=80, jalali=False, last_days=None):
    """A chart of the price over the window, then one line per day with its open, low, high and close.

    ``last_days`` limits the daily lines to the most recent ones.
    """
    title = history_title(key, days, toman)
    if not points:
        return f"{title}\n{NO_HISTORY}"
    points = [(stamp, rial_to_toman(price) if toman else price) for stamp, price in points]
    label_width = len(f"{max(price for _, price in points):,}")
    columns = max(10, min(width - label_width - 3, 200))
    values = resample(points, start, end, columns)
    chart = render_chart(values, start, end, height=CHART_HEIGHT, color=color, jalali=jalali)
    return "\n".join([title, "", chart, "", daily_summary(points, color=color, jalali=jalali, last=last_days)])


def format_history(key, days, changes, *, toman=False, color=False, jalali=False):
    title = history_title(key, days, toman)
    if not changes:
        return f"{title}\n{NO_HISTORY}"
    prices = [rial_to_toman(price) if toman else price for _, price in changes]
    width = len(f"{max(prices):,}")
    lines = [title, ""]
    previous = None
    for (stamp, _), price in zip(changes, prices):
        line = f"{format_stamp(stamp, jalali, seconds=True)}  {price:>{width},}"
        if previous is not None and price != previous:
            arrow, tint = ("▲", UP) if price > previous else ("▼", DOWN)
            move = f"{arrow} {abs(price - previous):,}"
            line += f"  {tint}{move}{RESET}" if color else f"  {move}"
        lines.append(line)
        previous = price
    summary = f"{len(prices)} price(s)   low {min(prices):,}   high {max(prices):,}   {sparkline(prices[-40:])}"
    lines += ["", summary.rstrip()]
    return "\n".join(lines)
