"""The run modes: print the table once, poll the feed and keep the table live, or list saved history."""

import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime

from tgju_rates.alerts import check_alerts, notify
from tgju_rates.ansi import ALERT_STYLE, DIM, DOWN, RESET, UP
from tgju_rates.controls import KEY_HELP, LiveControls
from tgju_rates.currencies import UNIT_NAMES, display_code, english_name, rial_to_toman
from tgju_rates.export import history_json, rates_json
from tgju_rates.holdings import TotalTrend, value_holdings
from tgju_rates.keys import KeyReader
from tgju_rates.screen import LiveScreen, print_frame
from tgju_rates.source import PAGE_URL, apply_live_prices, fetch_live_prices
from tgju_rates.table import render_holdings, render_table, sparkline
from tgju_rates.tracking import HIGHLIGHT_SECONDS, TREND_POINTS, PriceTracker

# How many fired alerts stay listed above the live table.
RECENT_ALERTS_SHOWN = 5


@dataclass(frozen=True)
class Options:
    persian: bool = False
    toman: bool = False
    json: bool = False


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
    print(f"Source: {PAGE_URL}   ({len(shown)} currencies)\n")
    if valuation:
        print(render_holdings(valuation, color=color, toman=options.toman) + "\n")
    print(render_table(shown, color=color, persian=options.persian, toman=options.toman))
    if fired:
        start, end = (ALERT_STYLE, RESET) if color else ("", "")
        print("\n" + "\n".join(f"{start}ALERT{end}  {message}" for message in fired))


def run_live(rates, shown, alerts, interval, options, history=None, holdings=()):
    """Poll forever. ``rates`` is every currency (alerts can watch any); ``shown`` is what's displayed."""
    if options.json:
        session = LiveSession(rates, shown, alerts, interval, options, color=False, history=history, holdings=holdings)
        session.run(lambda frame: print(frame, flush=True))
    elif not sys.stdout.isatty():
        session = LiveSession(rates, shown, alerts, interval, options, color=False, history=history, holdings=holdings)
        session.run(lambda frame: print_frame(frame.split("\n")))
    else:
        session = LiveSession(rates, shown, alerts, interval, options, color=True, history=history, holdings=holdings)
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


class LiveSession:
    def __init__(self, rates, shown, alerts, interval, options, color, history=None, holdings=()):
        self.rates, self.shown, self.alerts = rates, shown, alerts
        self.interval, self.options, self.color = interval, options, color
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
        self.updated_at = time.time()
        self.controls = LiveControls(toman=options.toman)
        self.interactive = False

    def run(self, draw, keys=None):
        """Poll every interval and redraw. With ``keys``, key presses redraw at once; ``q`` returns."""
        self.interactive = keys is not None
        next_poll = 0.0
        while True:
            if not self.controls.paused and time.time() >= next_poll:
                self.poll()
                next_poll = time.time() + self.interval
                draw(self.frame(time.time()))
            # While paused there's nothing to wait for but a key.
            wait = None if self.controls.paused else max(0.0, next_poll - time.time())
            if keys is None:
                time.sleep(wait)
                continue
            pressed = keys.read(wait)
            for key in pressed:
                self.controls.handle(key)
            if self.controls.quit:
                return
            if pressed:
                draw(self.frame(time.time()))

    def poll(self):
        now = self.updated_at = time.time()
        try:
            apply_live_prices(self.rates, fetch_live_prices())
            self.status = "connected"
        except (OSError, ValueError, KeyError) as error:
            self.status = f"feed error, retrying: {error}"
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

    def frame(self, now):
        if self.options.json:
            return rates_json(
                self.shown, now=now, toman=self.controls.toman, alerts=self.fired_alerts, valuation=self.valuation
            )
        dim_start, dim_end = (DIM, RESET) if self.color else ("", "")
        alert_start, alert_end = (ALERT_STYLE, RESET) if self.color else ("", "")
        stamp = datetime.fromtimestamp(self.updated_at).strftime("%H:%M:%S")
        watching = f"{dim_start}Watching {len(self.alerts)} alert(s).{dim_end}\n" if self.alerts else ""
        alert_lines = "".join(f"{alert_start}ALERT{alert_end} {line}\n" for line in self.recent_alerts)
        shown = self.controls.apply(self.shown)
        table = render_table(
            shown,
            color=self.color,
            persian=self.options.persian,
            toman=self.controls.toman,
            tracker=self.tracker,
            now=now,
        )
        savings = ""
        if self.valuation:
            trend = self.total_trend.values
            savings = render_holdings(self.valuation, color=self.color, toman=self.controls.toman, trend=trend)
            savings += "\n\n"
        state = "PAUSED" if self.controls.paused else f"every {self.interval:g}s"
        view = self.controls.describe()
        view_line = f"{view}\n" if view else ""
        key_help = f"{dim_start}Keys: {KEY_HELP}{dim_end}\n" if self.interactive else ""
        quit_hint = "" if self.interactive else "  Ctrl+C to quit."
        empty = "\nNo currency matches the filter." if self.controls.filter and not shown else ""
        return (
            f"tgju.org live rates   updated {stamp}   {state}   {self.status}\n"
            f"{dim_start}▲/▼ marks prices that moved in the last {HIGHLIGHT_SECONDS}s.  "
            f"TREND shows the last {TREND_POINTS} price changes.{quit_hint}{dim_end}\n"
            f"{key_help}"
            f"{view_line}{watching}{alert_lines}\n"
            f"{savings}{table}{empty}"
        )


def run_history(history, key, days, options, now=None):
    now = time.time() if now is None else now
    changes = history.changes_since(key, now - days * 86400)
    if options.json:
        print(history_json(key, changes, toman=options.toman))
        return
    print(format_history(key, days, changes, toman=options.toman, color=sys.stdout.isatty()))


def format_history(key, days, changes, *, toman=False, color=False):
    unit = UNIT_NAMES[toman]
    title = f"{display_code(key)} ({english_name(key)}), last {days:g} day(s), in {unit}"
    if not changes:
        return f"{title}\nNo saved prices. History is recorded while tgju-rates runs."
    prices = [rial_to_toman(price) if toman else price for _, price in changes]
    width = len(f"{max(prices):,}")
    lines = [title, ""]
    previous = None
    for (stamp, _), price in zip(changes, prices):
        line = f"{datetime.fromtimestamp(stamp):%Y-%m-%d %H:%M:%S}  {price:>{width},}"
        if previous is not None and price != previous:
            arrow, tint = ("▲", UP) if price > previous else ("▼", DOWN)
            move = f"{arrow} {abs(price - previous):,}"
            line += f"  {tint}{move}{RESET}" if color else f"  {move}"
        lines.append(line)
        previous = price
    summary = f"{len(prices)} price(s)   low {min(prices):,}   high {max(prices):,}   {sparkline(prices[-40:])}"
    lines += ["", summary.rstrip()]
    return "\n".join(lines)
