"""The two run modes: print the table once, or poll the feed and keep the table live."""

import sys
import time
from datetime import datetime

from tgju_rates.alerts import check_alerts, notify
from tgju_rates.ansi import ALERT_STYLE, DIM, RESET
from tgju_rates.screen import LiveScreen, print_frame
from tgju_rates.source import PAGE_URL, apply_live_prices, fetch_live_prices
from tgju_rates.table import render_table
from tgju_rates.tracking import HIGHLIGHT_SECONDS, TREND_POINTS, PriceTracker

# How many fired alerts stay listed above the live table.
RECENT_ALERTS_SHOWN = 5


def run_once(rates, shown, alerts, persian):
    color = sys.stdout.isatty()
    print(f"Source: {PAGE_URL}   ({len(shown)} currencies)\n")
    print(render_table(shown, color=color, persian=persian))
    fired = check_alerts(alerts, rates, set())
    if fired:
        start, end = (ALERT_STYLE, RESET) if color else ("", "")
        print("\n" + "\n".join(f"{start}ALERT{end}  {message}" for message in fired))


def run_live(rates, shown, alerts, interval, persian):
    """Poll forever. ``rates`` is every currency (alerts can watch any); ``shown`` is what's displayed."""
    if not sys.stdout.isatty():
        LiveSession(rates, shown, alerts, interval, persian, color=False).run(print_frame)
        return
    with LiveScreen() as screen:
        LiveSession(rates, shown, alerts, interval, persian, color=True).run(screen.draw)


class LiveSession:
    def __init__(self, rates, shown, alerts, interval, persian, color):
        self.rates, self.shown, self.alerts = rates, shown, alerts
        self.interval, self.persian, self.color = interval, persian, color
        self.tracker = PriceTracker()
        self.tracker.update(rates, time.time())
        self.active_alerts = set()
        self.recent_alerts = []
        self.status = "connected"

    def run(self, draw):
        while True:
            self.poll()
            draw(self.frame(time.time()).split("\n"))
            time.sleep(self.interval)

    def poll(self):
        try:
            apply_live_prices(self.rates, fetch_live_prices())
            self.status = "connected"
        except (OSError, ValueError, KeyError) as error:
            self.status = f"feed error, retrying: {error}"
        self.tracker.update(self.rates, time.time())
        stamp = datetime.now().strftime("%H:%M:%S")
        for message in check_alerts(self.alerts, self.rates, self.active_alerts):
            notify(message)
            self.recent_alerts.append(f"{stamp}  {message}")
        del self.recent_alerts[:-RECENT_ALERTS_SHOWN]

    def frame(self, now):
        dim_start, dim_end = (DIM, RESET) if self.color else ("", "")
        alert_start, alert_end = (ALERT_STYLE, RESET) if self.color else ("", "")
        stamp = datetime.fromtimestamp(now).strftime("%H:%M:%S")
        watching = f"{dim_start}Watching {len(self.alerts)} alert(s).{dim_end}\n" if self.alerts else ""
        alert_lines = "".join(f"{alert_start}ALERT{alert_end} {line}\n" for line in self.recent_alerts)
        table = render_table(self.shown, color=self.color, persian=self.persian, tracker=self.tracker, now=now)
        return (
            f"tgju.org live rates   updated {stamp}   every {self.interval:g}s   {self.status}\n"
            f"{dim_start}▲/▼ marks prices that moved in the last {HIGHLIGHT_SECONDS}s.  "
            f"TREND shows the last {TREND_POINTS} price changes.  Ctrl+C to quit.{dim_end}\n"
            f"{watching}{alert_lines}\n"
            f"{table}"
        )
