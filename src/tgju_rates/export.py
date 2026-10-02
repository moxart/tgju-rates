"""JSON output for scripts: ``--json`` prints rates and history as numbers instead of a table."""

import json
from datetime import datetime

from tgju_rates.currencies import (
    ENGLISH_NAMES,
    UNIT_NAMES,
    display_code,
    parse_change,
    parse_rial,
    rial_to_toman,
)
from tgju_rates.source import PAGE_URL


def in_unit(rial, toman):
    if rial is None:
        return None
    return rial_to_toman(rial) if toman else rial


def rate_record(rate, toman=False):
    change = parse_change(rate["change"])
    percent, amount = change if change else (None, None)
    return {
        "code": display_code(rate["key"]),
        "key": rate["key"],
        "name": ENGLISH_NAMES.get(rate["key"]),
        "persian_name": rate["name"],
        "price": in_unit(parse_rial(rate["price"]), toman),
        "change": in_unit(amount, toman),
        "change_percent": percent,
        "low": in_unit(parse_rial(rate["low"]), toman),
        "high": in_unit(parse_rial(rate["high"]), toman),
        "updated": rate["time"],
    }


def round_percent(value):
    return None if value is None else round(value, 2)


def holdings_record(valuation, toman=False):
    return {
        "items": [
            {
                "code": display_code(position.holding.key),
                "amount": position.holding.amount,
                "cost": in_unit(position.holding.cost, toman),
                "worth": in_unit(position.worth, toman),
                "gain_percent": round_percent(position.gain_percent),
                "today": in_unit(position.today, toman),
                "today_percent": round_percent(position.today_percent),
            }
            for position in valuation.positions
        ],
        "worth": in_unit(valuation.complete_worth, toman),
        "gain_percent": round_percent(valuation.gain_percent),
        "today": in_unit(valuation.today, toman),
        "today_percent": round_percent(valuation.today_percent),
    }


def rates_json(rates, *, now, toman=False, alerts=(), valuation=None):
    """One snapshot as a single-line JSON object, so live mode can emit JSON Lines."""
    snapshot = {
        "source": PAGE_URL,
        "time": datetime.fromtimestamp(now).astimezone().isoformat(timespec="seconds"),
        "unit": UNIT_NAMES[toman],
        "rates": [rate_record(rate, toman) for rate in rates],
        "alerts": list(alerts),
    }
    if valuation is not None:
        snapshot["holdings"] = holdings_record(valuation, toman)
    return json.dumps(snapshot, ensure_ascii=False)


def history_json(key, changes, *, toman=False):
    return json.dumps(
        {
            "code": display_code(key),
            "unit": UNIT_NAMES[toman],
            "prices": [
                {
                    "time": datetime.fromtimestamp(time).astimezone().isoformat(timespec="seconds"),
                    "price": in_unit(price, toman),
                }
                for time, price in changes
            ],
        },
        ensure_ascii=False,
    )
