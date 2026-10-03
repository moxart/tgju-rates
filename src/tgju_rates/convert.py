"""``--convert "250 usd"``: turn an amount of one currency into rial, toman or another currency.

Prices come from the feed, which carries every currency, coin and crypto, so no page is scraped.
When the feed can't be reached, the last prices saved in the history file are used instead.
"""

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from tgju_rates.currencies import (
    RIAL_PER_TOMAN,
    UNIT_SIZE,
    display_code,
    english_name,
    parse_rial,
    row_key,
)
from tgju_rates.source import fetch_live_prices

MONEY_UNITS = {"rial": 1, "irr": 1, "toman": RIAL_PER_TOMAN}
# Words allowed between the units: "250 usd to eur", "250 usd in toman".
FILLER_WORDS = {"to", "in", "="}
AMOUNT_PATTERN = re.compile(r"^\d[\d,]*(?:\.\d+)?$")
EXAMPLE = '"250 usd", "250 usd eur" or "50,000,000 toman to usd"'


@dataclass(frozen=True)
class Conversion:
    amount: float
    source: str  # a row key, or "rial" / "toman"
    target: str = ""  # same; "" means rial and toman both


def unit_of(word):
    word = word.lower()
    if word in MONEY_UNITS:
        return "toman" if word == "toman" else "rial"
    return row_key(word)


def parse_conversion(text):
    """Parse ``AMOUNT [UNIT] [to] [UNIT]``. Raises ValueError."""
    words = [word for word in text.split() if word.lower() not in FILLER_WORDS]
    if not words or not AMOUNT_PATTERN.match(words[0]) or not 2 <= len(words) <= 3:
        raise ValueError(f"{text!r} is not a conversion; try {EXAMPLE}")
    amount = float(words[0].replace(",", ""))
    units = [unit_of(word) for word in words[1:]]
    if len(units) == 1 and units[0] in MONEY_UNITS:
        raise ValueError(f"{text!r} doesn't say what to convert {units[0]} into; try {EXAMPLE}")
    return Conversion(amount, *units)


def rial_per_unit(unit, prices):
    """Rial for one unit of ``unit`` (one yen, not the site's 100); raises KeyError for an unknown code."""
    if unit in MONEY_UNITS:
        return MONEY_UNITS[unit]
    return prices[unit] / UNIT_SIZE.get(unit, 1)


def convert(conversion, prices):
    """{target unit: amount} for the conversion, with ``prices`` as {row key: rial price}."""
    rial = conversion.amount * rial_per_unit(conversion.source, prices)
    targets = [conversion.target] if conversion.target else ["rial", "toman"]
    return {target: rial / rial_per_unit(target, prices) for target in targets}


def unit_label(unit):
    if unit in MONEY_UNITS:
        return unit
    return display_code(unit)


def format_quantity(value, unit):
    if unit in MONEY_UNITS:
        return f"{round(value):,}"
    if abs(value) >= 1:
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    return f"{value:.6g}"


def format_conversion(conversion, results, prices, note=""):
    amount = format_quantity(conversion.amount, conversion.source)
    sides = " = ".join(f"{format_quantity(value, unit)} {unit_label(unit)}" for unit, value in results.items())
    lines = [f"{amount} {unit_label(conversion.source)} = {sides}"]
    for unit in dict.fromkeys([conversion.source, *results]):
        if unit not in MONEY_UNITS:
            size = UNIT_SIZE.get(unit, 1)
            lines.append(f"  {size:,} {unit_label(unit)} ({english_name(unit)}) = {prices[unit]:,} rial")
    if note:
        lines.append(note)
    return "\n".join(lines)


def whole(number):
    return int(number) if float(number).is_integer() else number


def conversion_json(conversion, results, prices, note=""):
    return json.dumps(
        {
            "amount": whole(conversion.amount),
            "from": unit_label(conversion.source),
            "results": {
                unit_label(unit): round(value) if unit in MONEY_UNITS else value for unit, value in results.items()
            },
            "prices_rial": {
                unit_label(unit): prices[unit] for unit in [conversion.source, *results] if unit not in MONEY_UNITS
            },
            "note": note or None,
        },
        ensure_ascii=False,
    )


def live_prices(keys):
    """{key: rial price} from the feed for the keys it has with a rial price."""
    live = fetch_live_prices()
    prices = {key: parse_rial(live[key]["p"]) for key in keys if key in live}
    return {key: price for key, price in prices.items() if price is not None}


def saved_prices(history, keys):
    """{key: rial price} from the history file, and the oldest of their save times."""
    latest = history.latest() if history is not None else {}
    found = {key: latest[key] for key in keys if key in latest}
    oldest = min((stamp for stamp, _ in found.values()), default=None)
    return {key: price for key, (_, price) in found.items()}, oldest


def run_convert(text, history=None, as_json=False):
    """Print the conversion; returns an error message instead when it can't be done."""
    conversion = parse_conversion(text)
    keys = [unit for unit in (conversion.source, conversion.target) if unit and unit not in MONEY_UNITS]
    note = ""
    try:
        prices = live_prices(keys)
    except (OSError, ValueError, KeyError) as error:
        try:
            prices, oldest = saved_prices(history, keys)
        except sqlite3.Error:
            prices, oldest = {}, None
        when = f" from {datetime.fromtimestamp(oldest):%Y-%m-%d %H:%M}" if oldest else ""
        note = f"Feed unavailable ({error}); using saved prices{when}."
    missing = [key for key in keys if key not in prices]
    if missing:
        codes = ", ".join(display_code(key).lower() for key in missing)
        return f"No price for {codes}." + (f" {note}" if note else "")
    results = convert(conversion, prices)
    show = conversion_json if as_json else format_conversion
    print(show(conversion, results, prices, note))
    return None
