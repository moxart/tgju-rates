"""Price alerts such as ``usd>2600000``, and desktop notifications when they fire."""

import operator
import re
import shutil
import subprocess
from dataclasses import dataclass

from tgju_rates.currencies import display_code, parse_rial, row_key

ALERT_PATTERN = re.compile(r"^\s*(\w+)\s*(>=|<=|>|<)\s*([\d,]+)\s*$")
COMPARISONS = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le}


@dataclass(frozen=True)
class Alert:
    key: str
    op: str
    limit: int  # in rial

    def holds(self, price):
        return COMPARISONS[self.op](price, self.limit)

    def __str__(self):
        return f"{display_code(self.key)} {self.op} {self.limit:,}"


def parse_alert(text):
    match = ALERT_PATTERN.match(text)
    if not match:
        raise ValueError(f"{text!r} is not an alert; expected something like usd>2600000")
    code, op, limit = match.groups()
    return Alert(row_key(code), op, int(limit.replace(",", "")))


def check_alerts(alerts, rates, active):
    """Return messages for the alerts that just became true.

    Each alert fires once, then re-arms after its condition stops holding. ``active`` holds the
    alerts currently firing and is updated in place between calls.
    """
    prices = {rate["key"]: parse_rial(rate["price"]) for rate in rates}
    fired = []
    for alert in alerts:
        price = prices.get(alert.key)
        if price is None:
            continue
        if not alert.holds(price):
            active.discard(alert)
        elif alert not in active:
            active.add(alert)
            fired.append(f"{display_code(alert.key)} is {price:,} rial  (alert: {alert})")
    return fired


def notify(message):
    """Show a desktop notification where notify-send exists; the live screen lists alerts either way."""
    if not shutil.which("notify-send"):
        return
    try:
        subprocess.run(["notify-send", "--app-name=tgju rates", "Currency alert", message], check=False, timeout=5)
    except (OSError, subprocess.SubprocessError):
        pass
