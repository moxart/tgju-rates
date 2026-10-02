"""Command-line entry point: ``tgju-rates`` or ``python -m tgju_rates``."""

import argparse
import signal
import sys

from tgju_rates import __version__
from tgju_rates.alerts import parse_alert
from tgju_rates.app import run_live, run_once
from tgju_rates.currencies import display_code, row_key
from tgju_rates.source import PAGE_URL, scrape_page_rates

DEFAULT_INTERVAL = 10
MIN_INTERVAL = 3


def alert_argument(text):
    try:
        return parse_alert(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from None


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
    parser.add_argument(
        "--watch", metavar="CODES", help="comma-separated currency codes to show, in this order (e.g. usd,eur,gbp)"
    )
    parser.add_argument(
        "--alert",
        metavar="RULE",
        type=alert_argument,
        action="append",
        default=[],
        help="notify when a price in rial crosses a limit, e.g. usd>2600000 or eur<=2,850,000 (repeatable)",
    )
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


def main(argv=None):
    args = build_parser().parse_args(argv)
    # Exit through KeyboardInterrupt on SIGTERM too, so live mode restores the terminal.
    signal.signal(signal.SIGTERM, signal.default_int_handler)

    try:
        rates = scrape_page_rates()
    except OSError as error:
        sys.exit(f"Could not fetch {PAGE_URL}: {error}")
    if not rates:
        sys.exit("No rates found. The page layout may have changed.")

    by_key = {rate["key"]: rate for rate in rates}
    watch_keys = parse_watch(args.watch)
    exit_if_unknown(by_key, watch_keys + [alert.key for alert in args.alert])
    shown = [by_key[key] for key in watch_keys] or rates

    if args.once:
        run_once(rates, shown, args.alert, args.persian)
        return
    try:
        run_live(rates, shown, args.alert, max(args.interval, MIN_INTERVAL), args.persian)
    except KeyboardInterrupt:
        print("\nStopped.")
