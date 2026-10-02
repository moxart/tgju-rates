"""Your savings: amounts of each currency you hold, valued at live prices.

Holdings come from a file (one per line) and from ``--hold`` options, both written as
``code=amount`` or ``code=amount@price``, where price is what you paid per unit.
"""

import os
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tgju_rates.currencies import RIAL_PER_TOMAN, parse_change, parse_rial, row_key

HOLDING_PATTERN = re.compile(
    r"^\s*(\w+)\s*=\s*([\d,]+(?:\.\d+)?)\s*(?:@\s*([\d,]+)\s*(toman|rial)?)?\s*$", re.IGNORECASE
)
# How far back the history file is read to seed the TOTAL sparkline.
TREND_SEED_SECONDS = 7 * 86400
EXAMPLE = "usd=1200@2,450,000"


@dataclass(frozen=True)
class Holding:
    key: str
    amount: float
    cost: Optional[int] = None  # rial paid per unit, if known


@dataclass(frozen=True)
class Position:
    holding: Holding
    worth: Optional[int] = None  # rial; None when the price is unknown
    gain_percent: Optional[float] = None  # since bought
    today: Optional[int] = None  # rial change in worth today
    today_percent: Optional[float] = None


@dataclass(frozen=True)
class Valuation:
    positions: list
    worth: int
    gain_percent: Optional[float] = None  # over the holdings with a known cost
    today: int = 0
    today_percent: Optional[float] = None

    @property
    def complete_worth(self):
        """The total, or None while any holding's price is unknown (a partial total would mislead alerts)."""
        return self.worth if all(position.worth is not None for position in self.positions) else None


def default_holdings_path():
    config_home = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(config_home) / "tgju-rates" / "holdings.txt"


def parse_holding(text, toman=False):
    """Parse ``usd=1200@2,450,000``. A price without a unit is toman with ``toman``, else rial."""
    match = HOLDING_PATTERN.match(text)
    if not match:
        raise ValueError(f"{text!r} is not a holding; expected something like {EXAMPLE}")
    code, amount, price, unit = match.groups()
    cost = None
    if price is not None:
        in_toman = unit.lower() == "toman" if unit else toman
        cost = int(price.replace(",", "")) * (RIAL_PER_TOMAN if in_toman else 1)
    amount = float(amount.replace(",", ""))
    return Holding(row_key(code), int(amount) if amount.is_integer() else amount, cost)


def load_holdings(path):
    """Read a holdings file; a missing file means no holdings. Raises ValueError naming the bad line.

    A price without a unit is rial here, whatever --toman says, so the file means the same on every run.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    holdings = []
    for number, line in enumerate(text.splitlines(), 1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        try:
            holdings.append(parse_holding(line))
        except ValueError as error:
            raise ValueError(f"{path}, line {number}: {error}") from None
    return holdings


def merge_holdings(from_file, from_options):
    """Combine both sources; a --hold for a currency replaces the file's line for it."""
    merged = {holding.key: holding for holding in from_file}
    merged.update((holding.key, holding) for holding in from_options)
    return list(merged.values())


def percent(change, base):
    return change / base * 100 if base else None


def value_holdings(holdings, rates):
    by_key = {rate["key"]: rate for rate in rates}
    positions = []
    for holding in holdings:
        rate = by_key.get(holding.key)
        price = parse_rial(rate["price"]) if rate else None
        if price is None:
            positions.append(Position(holding))
            continue
        worth = round(holding.amount * price)
        change = parse_change(rate["change"])
        today = round(holding.amount * change[1]) if change else None
        gain = percent(worth - holding.amount * holding.cost, holding.amount * holding.cost) if holding.cost else None
        positions.append(Position(holding, worth, gain, today, change[0] if change else None))
    priced = [position for position in positions if position.worth is not None]
    worth = sum(position.worth for position in priced)
    costed = [position for position in priced if position.holding.cost]
    paid = sum(position.holding.amount * position.holding.cost for position in costed)
    gain = percent(sum(position.worth for position in costed) - paid, paid) if costed else None
    today = sum(position.today or 0 for position in priced)
    return Valuation(positions, worth, gain, today, percent(today, worth - today))


def total_worth(holdings, prices):
    """Total in rial from a {key: rial price} dict, or None until every holding has a price."""
    if any(prices.get(holding.key) is None for holding in holdings):
        return None
    return round(sum(holding.amount * prices[holding.key] for holding in holdings))


class TotalTrend:
    """The last few distinct totals, for the TOTAL row's sparkline (like PriceTracker's trends)."""

    def __init__(self, points):
        self.values = deque(maxlen=points)

    def add(self, total):
        if total is not None and (not self.values or self.values[-1] != total):
            self.values.append(total)

    def seed(self, history, holdings, now):
        """Rebuild past totals from saved prices: replay every change in time order."""
        start = now - TREND_SEED_SECONDS
        events = sorted(
            (time, holding.key, price)
            for holding in holdings
            for time, price in history.changes_since(holding.key, start)
        )
        prices = {}
        for _, key, price in events:
            prices[key] = price
            self.add(total_worth(holdings, prices))
