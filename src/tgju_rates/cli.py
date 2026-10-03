"""Command-line entry point: ``tgju-rates`` or ``python -m tgju_rates``."""

import argparse
import os
import signal
import sqlite3
import sys

from tgju_rates import __version__
from tgju_rates.alerts import TOTAL_KEY, parse_alert
from tgju_rates.animation import ANIMATIONS, DEFAULT_ANIMATION
from tgju_rates.app import HISTORY_VIEWS, Options, run_history, run_live, run_once, saved_rates
from tgju_rates.completion import SHELLS, completion_script
from tgju_rates.convert import parse_conversion, run_convert
from tgju_rates.currencies import display_code, row_key
from tgju_rates.doctor import run_doctor
from tgju_rates.history import History, default_path
from tgju_rates.holdings import default_holdings_path, load_holdings, merge_holdings, parse_holding
from tgju_rates.markets import CURRENCY, FEED_MARKETS, market_of, parse_markets
from tgju_rates.source import apply_live_prices, fetch_live_prices, load_markets

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


def market_argument(text):
    try:
        return parse_markets(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from None


def convert_argument(text):
    try:
        parse_conversion(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from None
    return text


def market_codes_epilog():
    lines = [f"{market:<7} {', '.join(item.code for item in items)}" for market, items in FEED_MARKETS.items()]
    return "codes beyond currencies:\n  " + "\n  ".join(lines)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="tgju-rates",
        description="Live currency, gold coin, gold and crypto rates from tgju.org",
        epilog=market_codes_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
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
        "--animation",
        choices=ANIMATIONS,
        default=DEFAULT_ANIMATION,
        help="effect on a price that just changed, in live mode in a terminal: flash (background), glow (text), "
        f"roll (spinning digits), board (roll and flash), or off (default {DEFAULT_ANIMATION}; 'a' cycles them)",
    )
    parser.add_argument(
        "--market",
        metavar="MARKETS",
        type=market_argument,
        default=[CURRENCY],
        help="comma-separated markets to show: currency, coin, gold, crypto, or all (default currency)",
    )
    parser.add_argument(
        "--watch",
        metavar="CODES",
        help="comma-separated codes to show, in this order (e.g. usd,eur,emami); fetches their markets as needed",
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
    views = history.add_mutually_exclusive_group()
    views.add_argument("--chart", action="store_true", help="show --history as a chart with a daily summary")
    views.add_argument("--csv", action="store_true", help="print --history as CSV")
    history.add_argument("--db", metavar="PATH", help=f"history file (default {default_path()})")
    history.add_argument("--no-record", action="store_true", help="don't save prices to the history file")
    parser.add_argument(
        "--convert",
        metavar="TEXT",
        type=convert_argument,
        help='convert an amount and exit, e.g. "250 usd", "250 usd eur" or "50,000,000 toman to btc"',
    )
    parser.add_argument("--doctor", action="store_true", help="check that tgju.org still works with this program")
    parser.add_argument("--completion", choices=SHELLS, help="print a shell completion script and exit")
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
            f"Unknown currency code: {', '.join(display_code(k).lower() for k in unknown)}\nAvailable: {available}\n"
            + market_codes_epilog()
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
    parser = build_parser()
    args = parser.parse_args(argv)
    if (args.chart or args.csv) and not args.history:
        parser.error("--chart and --csv go with --history")
    options = Options(persian=args.persian, toman=args.toman, json=args.json, animation=args.animation)
    db_path = args.db or default_path()

    if args.completion:
        print(completion_script(args.completion, parser), end="")
        return
    if args.doctor:
        sys.exit(run_doctor(db_path, args.holdings or default_holdings_path(), color=sys.stdout.isatty()))
    if args.history:
        history = open_history(db_path, required=True)
        view = HISTORY_VIEWS[1] if args.chart else HISTORY_VIEWS[2] if args.csv else HISTORY_VIEWS[0]
        try:
            run_history(history, row_key(args.history), args.days, options, view=view)
        finally:
            history.close()
        return
    if args.convert:
        history = existing_history(db_path)
        try:
            error = run_convert(args.convert, history, as_json=args.json)
        finally:
            if history is not None:
                history.close()
        if error:
            sys.exit(error)
        return

    # Exit through KeyboardInterrupt on SIGTERM too, so live mode restores the terminal.
    signal.signal(signal.SIGTERM, signal.default_int_handler)
    history = None if args.no_record else open_history(db_path, required=False)
    try:
        run(args, options, history)
    finally:
        if history is not None:
            history.close()


def existing_history(path):
    """The history file if it already exists, for reading saved prices; None otherwise."""
    if str(path) != ":memory:" and not os.path.exists(path):
        return None
    try:
        return History.open(path)
    except (OSError, sqlite3.Error):
        return None


def load_rates(markets, history, db_path):
    """Starting rows for ``markets``, falling back to saved prices for a market that can't be loaded.

    Returns ({market: rates}, notice); the notice says what came from the history file, or is "".
    Exits when a market can't be loaded and nothing was saved for it.
    """
    loaded, errors = load_markets(markets)
    if not errors:
        return loaded, ""
    saved_from = history if history is not None else existing_history(db_path)
    fallback = saved_rates(saved_from, list(errors)) if saved_from is not None else []
    if saved_from is not None and saved_from is not history:
        saved_from.close()
    if not fallback:
        sys.exit("\n".join(f"Could not load {market}: {error}" for market, error in errors.items()))
    try:
        apply_live_prices(fallback, fetch_live_prices())
        freshness = "prices are live from the feed"
    except (OSError, ValueError, KeyError):
        freshness = f"prices are the last saved ones, up to {max(rate['time'] for rate in fallback)}"
    for rate in fallback:
        loaded.setdefault(market_of(rate["key"]), []).append(rate)
    problems = "; ".join(errors.values())
    return loaded, f"{problems}. Using the list saved in the history file; {freshness}."


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
    watch_keys = parse_watch(args.watch)
    alert_keys = [alert.key for alert in alerts if alert.key != TOTAL_KEY]
    wanted = watch_keys + alert_keys + [holding.key for holding in holdings]
    # Shown markets first, then any other market a watched, alerted or held code needs.
    markets = list(dict.fromkeys([*args.market, *(market_of(key) for key in wanted)]))
    loaded, notice = load_rates(markets, history, args.db or default_path())
    if notice:
        print(f"Note: {notice}", file=sys.stderr)
    rates = [rate for market in markets for rate in loaded.get(market, [])]

    by_key = {rate["key"]: rate for rate in rates}
    exit_if_unknown(by_key, wanted)
    shown = [by_key[key] for key in watch_keys] or [rate for market in args.market for rate in loaded.get(market, [])]

    if args.once:
        run_once(rates, shown, alerts, options, history, holdings)
        return
    try:
        run_live(rates, shown, alerts, max(args.interval, MIN_INTERVAL), options, history, holdings, notice)
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
