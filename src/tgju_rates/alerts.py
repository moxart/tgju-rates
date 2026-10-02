"""Price alerts such as ``usd>2600000``, and desktop notifications when they fire."""

import operator
import re
import shutil
import subprocess
from dataclasses import dataclass

from tgju_rates.currencies import RIAL_PER_TOMAN, display_code, format_amount, parse_rial, rial_to_toman, row_key

ALERT_PATTERN = re.compile(r"^\s*(\w+)\s*(>=|<=|>|<)\s*([\d,]+)\s*$")
COMPARISONS = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le}
# "total>5000000000" watches the value of your holdings instead of one currency's price.
TOTAL_KEY = "total"


@dataclass(frozen=True)
class Alert:
    key: str
    op: str
    limit: int  # in rial

    def holds(self, price):
        return COMPARISONS[self.op](price, self.limit)

    def describe(self, toman=False):
        limit = rial_to_toman(self.limit) if toman else self.limit
        return f"{display_code(self.key)} {self.op} {limit:,}"

    def __str__(self):
        return self.describe()


def parse_alert(text, toman=False):
    """Parse a rule like ``usd>2600000`` or ``total>5000000000``.

    With ``toman`` the limit is read as toman and stored in rial.
    """
    match = ALERT_PATTERN.match(text)
    if not match:
        raise ValueError(f"{text!r} is not an alert; expected something like usd>2600000")
    code, op, limit = match.groups()
    multiplier = RIAL_PER_TOMAN if toman else 1
    key = TOTAL_KEY if code.lower() == TOTAL_KEY else row_key(code)
    return Alert(key, op, int(limit.replace(",", "")) * multiplier)


def check_alerts(alerts, rates, active, toman=False, total=None):
    """Return messages for the alerts that just became true.

    Each alert fires once, then re-arms after its condition stops holding. ``active`` holds the
    alerts currently firing and is updated in place between calls. ``total`` is the holdings' worth
    in rial, for ``total`` alerts.
    """
    prices = {rate["key"]: parse_rial(rate["price"]) for rate in rates}
    prices[TOTAL_KEY] = total
    fired = []
    for alert in alerts:
        price = prices.get(alert.key)
        if price is None:
            continue
        if not alert.holds(price):
            active.discard(alert)
        elif alert not in active:
            active.add(alert)
            fired.append(
                f"{display_code(alert.key)} is {format_amount(price, toman)}  (alert: {alert.describe(toman)})"
            )
    return fired


def notify(message):
    """Show a desktop notification where notify-send exists; the live screen lists alerts either way."""
    if not shutil.which("notify-send"):
        return
    try:
        subprocess.run(["notify-send", "--app-name=tgju rates", "Currency alert", message], check=False, timeout=5)
    except (OSError, subprocess.SubprocessError):
        pass
