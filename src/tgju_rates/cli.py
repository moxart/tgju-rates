"""Command-line entry point: ``tgju-rates`` or ``python -m tgju_rates``."""

import argparse
import signal
import sqlite3
import sys

from tgju_rates import __version__
from tgju_rates.alerts import TOTAL_KEY, parse_alert
from tgju_rates.app import Options, run_history, run_live, run_once
from tgju_rates.currencies import display_code, row_key
from tgju_rates.history import History, default_path
from tgju_rates.holdings import default_holdings_path, load_holdings, merge_holdings, parse_holding
from tgju_rates.source import PAGE_URL, scrape_page_rates

DEFAULT_INTERVAL = 10
MIN_INTERVAL = 3


def alert_argument(text):
    """Check the rule's syntax now; it's parsed in main(), once --toman tells which unit the limit is in."""
    try:
        parse_alert(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from None
    return text


def hold_argument(text):
    """Check the holding's syntax now; like alerts, it's parsed once --toman is known."""
    try:
        parse_holding(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from None
    return text


def build_parser():
    parser = argparse.ArgumentParser(prog="tgju-rates", description="Live currency rates from tgju.org")
    parser.add_argument(
        "-i",
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL,
        help=f"seconds between updates (default {DEFAULT_INTERVAL}, min {MIN_INTERVAL})",
    )
    parser.add_argument("--once", action="store_true", help="print the table once and exit")
    parser.add_argument("--persian", action="store_true", help="also show the Persian names from the page")
    parser.add_argument("--toman", action="store_true", help="show prices in toman, and read --alert limits as toman")
    parser.add_argument(
        "--json", action="store_true", help="print JSON instead of a table (one JSON object per update when live)"
    )
    parser.add_argument(
        "--watch", metavar="CODES", help="comma-separated currency codes to show, in this order (e.g. usd,eur,gbp)"
    )
    parser.add_argument(
        "--alert",
        metavar="RULE",
        type=alert_argument,
        action="append",
        default=[],
        help="notify when a price crosses a limit in rial (toman with --toman), e.g. usd>2600000 (repeatable); "
        "total>LIMIT watches your savings",
    )
    savings = parser.add_argument_group(
        "savings",
        "Show what the currencies you hold are worth. Write each as CODE=AMOUNT, or CODE=AMOUNT@PRICE with "
        "the price you paid per unit. Add 'toman' or 'rial' after the price to be explicit; otherwise --hold "
        "prices follow --toman, and file prices are rial.",
    )
    savings.add_argument(
        "--hold",
        metavar="HOLDING",
        type=hold_argument,
        action="append",
        default=[],
        help="a currency you hold, e.g. usd=1200@2,450,000 (repeatable; replaces the file's line for that currency)",
    )
    savings.add_argument(
        "--holdings",
        metavar="PATH",
        help=f"holdings file, one per line, # for comments (default {default_holdings_path()})",
    )
    history = parser.add_argument_group("history", "Prices are saved to a local SQLite file whenever they change.")
    history.add_argument("--history", metavar="CODE", help="list the saved prices of one currency and exit")
    history.add_argument("--days", type=float, default=1, help="how far back --history goes, in days (default 1)")
    history.add_argument("--db", metavar="PATH", help=f"history file (default {default_path()})")
    history.add_argument("--no-record", action="store_true", help="don't save prices to the history file")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def parse_watch(watch):
    """Turn a --watch value like "usd,eur" into row keys, keeping the user's order."""
    return list(dict.fromkeys(row_key(code) for code in watch.split(",") if code.strip())) if watch else []


def exit_if_unknown(by_key, keys):
    unknown = [key for key in keys if key not in by_key]
    if unknown:
        available = ", ".join(sorted(display_code(key).lower() for key in by_key) + ["usd"])
        sys.exit(
            f"Unknown currency code: {', '.join(display_code(k).lower() for k in unknown)}\nAvailable: {available}"
        )


def open_history(path, required):
    """Open the history file; if it can't be opened, live mode carries on without it."""
    try:
        return History.open(path)
    except (OSError, sqlite3.Error) as error:
        if required:
            sys.exit(f"Could not open history file {path}: {error}")
        print(f"Warning: not saving history, could not open {path}: {error}", file=sys.stderr)
        return None


def main(argv=None):
    args = build_parser().parse_args(argv)
    options = Options(persian=args.persian, toman=args.toman, json=args.json)
    db_path = args.db or default_path()

    if args.history:
        history = open_history(db_path, required=True)
        try:
            run_history(history, row_key(args.history), args.days, options)
        finally:
            history.close()
        return

    # Exit through KeyboardInterrupt on SIGTERM too, so live mode restores the terminal.
    signal.signal(signal.SIGTERM, signal.default_int_handler)
    history = None if args.no_record else open_history(db_path, required=False)
    try:
        run(args, options, history)
    finally:
        if history is not None:
            history.close()


def read_holdings(args):
    try:
        from_file = load_holdings(args.holdings or default_holdings_path())
    except (OSError, ValueError) as error:
        sys.exit(f"Could not read holdings: {error}")
    return merge_holdings(from_file, [parse_holding(text, toman=args.toman) for text in args.hold])


def run(args, options, history):
    alerts = [parse_alert(text, toman=args.toman) for text in args.alert]
    holdings = read_holdings(args)
    if not holdings and any(alert.key == TOTAL_KEY for alert in alerts):
        sys.exit("A total alert needs holdings: use --hold or a holdings file.")
    try:
        rates = scrape_page_rates()
    except OSError as error:
        sys.exit(f"Could not fetch {PAGE_URL}: {error}")
    if not rates:
        sys.exit("No rates found. The page layout may have changed.")

    by_key = {rate["key"]: rate for rate in rates}
    watch_keys = parse_watch(args.watch)
    alert_keys = [alert.key for alert in alerts if alert.key != TOTAL_KEY]
    exit_if_unknown(by_key, watch_keys + alert_keys + [holding.key for holding in holdings])
    shown = [by_key[key] for key in watch_keys] or rates

    if args.once:
        run_once(rates, shown, alerts, options, history, holdings)
        return
    try:
        run_live(rates, shown, alerts, max(args.interval, MIN_INTERVAL), options, history, holdings)
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
