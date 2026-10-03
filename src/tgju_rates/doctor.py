"""``--doctor``: check that tgju.org's page and feed still look the way this program expects.

Each check prints one line marked ok, warn or FAIL. A failure means the program can't work as is
(no network, or the site changed its markup or feed); a warning means something is missing that
the program copes with, such as a new currency without an English name.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

from tgju_rates.ansi import DOWN, RESET, UP
from tgju_rates.currencies import ENGLISH_NAMES, display_code, parse_rial
from tgju_rates.holdings import load_holdings
from tgju_rates.markets import FEED_MARKETS
from tgju_rates.source import FEED_URL, PAGE_URL, fetch_live_prices, scrape_page_rates

OK, WARN, FAIL = "ok", "warn", "FAIL"
WARN_STYLE = "\033[38;5;214m"
MARK_STYLES = {OK: UP, WARN: WARN_STYLE, FAIL: DOWN}


def codes(keys):
    return ", ".join(display_code(key).lower() for key in keys)


def check_page():
    try:
        rates = scrape_page_rates()
    except OSError as error:
        return [(FAIL, f"currency page: could not fetch {PAGE_URL}: {error}")], []
    if not rates:
        return [(FAIL, f"currency page: no rows found on {PAGE_URL}; the markup has probably changed")], []
    results = [(OK, f"currency page: {len(rates)} currencies")]
    unnamed = [rate["key"] for rate in rates if rate["key"] not in ENGLISH_NAMES]
    if unnamed:
        results.append((WARN, f"currencies without an English name (shown as '-'): {codes(unnamed)}"))
    return results, rates


def check_feed():
    try:
        live = fetch_live_prices()
    except (OSError, ValueError, KeyError) as error:
        return [(FAIL, f"feed: could not read {FEED_URL}: {error}")], None
    return [(OK, f"feed: {len(live)} prices")], live


def check_feed_entries(keys, live, label):
    """Whether the feed has a usable rial price (and the fields the program reads) for each key."""
    missing = [key for key in keys if key not in live]
    broken = [
        key
        for key in keys
        if key in live
        and (parse_rial(str(live[key].get("p", ""))) is None or not {"l", "h", "d", "dp"} <= live[key].keys())
    ]
    found = len(keys) - len(missing) - len(broken)
    status = OK if not missing and not broken else WARN if found else FAIL
    line = f"{label}: {found}/{len(keys)} in the feed"
    if missing:
        line += f"; missing: {codes(missing)}"
    if broken:
        line += f"; unexpected format: {codes(broken)}"
    return [(status, line)]


def check_history(path):
    path = Path(path)
    if not path.exists():
        return [(OK, f"history: no file yet at {path} (created on the first run)")]
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            count, last = connection.execute("SELECT COUNT(*), MAX(time) FROM prices").fetchone()
        finally:
            connection.close()
    except sqlite3.Error as error:
        return [(FAIL, f"history: could not read {path}: {error}")]
    when = f", last saved {datetime.fromtimestamp(last):%Y-%m-%d %H:%M}" if last else ""
    return [(OK, f"history: {count:,} saved prices in {path}{when}")]


def check_holdings(path):
    try:
        holdings = load_holdings(path)
    except (OSError, ValueError) as error:
        return [(FAIL, f"holdings: {error}")]
    if not holdings:
        return [(OK, f"holdings: none ({path} doesn't exist or is empty)")]
    return [(OK, f"holdings: {len(holdings)} in {path} ({codes(holding.key for holding in holdings)})")]


def run_doctor(history_path, holdings_path, color=False):
    """Run every check and print the results; returns the process exit code (1 if anything failed)."""
    results, rates = check_page()
    feed_results, live = check_feed()
    results += feed_results
    if live is not None:
        if rates:
            results += check_feed_entries([rate["key"] for rate in rates], live, "currencies")
        for market, items in FEED_MARKETS.items():
            results += check_feed_entries([item.key for item in items], live, market)
    results += check_history(history_path)
    results += check_holdings(holdings_path)
    for status, message in results:
        mark = f"{status:<4}"
        if color:
            mark = f"{MARK_STYLES[status]}{mark}{RESET}"
        print(f"{mark}  {message}")
    return 1 if any(status == FAIL for status, _ in results) else 0
