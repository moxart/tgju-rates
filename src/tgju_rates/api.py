"""The JSON API behind ``--serve``, without the HTTP: ``Api.handle(path, params)`` gives a status and a payload.

Keeping the web server out of this module (it lives in server.py) means the same routes can later sit
behind another server, with authentication or rate limits added there, without changing the responses.

Every price is a whole number in rial, or toman with ``?unit=toman``. Responses about current prices say
when the feed was last read (``updated``) and whether that's too long ago (``stale``).
"""

import math
import threading
import time

from tgju_rates import __version__
from tgju_rates.app import record_history, retry_delay
from tgju_rates.convert import MONEY_UNITS, Conversion, conversion_record, convert, missing_prices, unit_of
from tgju_rates.currencies import UNIT_NAMES, display_code, parse_codes, parse_rial, row_key
from tgju_rates.export import history_record, iso_time, rate_record
from tgju_rates.jewelry import DEFAULT_PROFIT, DEFAULT_TAX, GOLD_KEY, Piece, quote, quote_record
from tgju_rates.markets import market_of, parse_markets
from tgju_rates.source import apply_live_prices, fetch_live_prices

API_PREFIX = "/v1"
ENDPOINTS = (
    "GET /v1/rates?market=currency,coin,gold,crypto&codes=usd,eur&unit=rial|toman",
    "GET /v1/rates/{code}?unit=rial|toman",
    "GET /v1/history/{code}?days=1&unit=rial|toman",
    "GET /v1/convert?amount=250&from=usd&to=eur",
    "GET /v1/jewelry?weight=12.5&wage=18&profit=7&tax=10",
    "GET /v1/health",
)
OK, BAD_REQUEST, NOT_FOUND, SERVICE_UNAVAILABLE = 200, 400, 404, 503
# Prices count as stale once this many poll intervals pass without a successful read of the feed.
STALE_POLLS = 3
MAX_HISTORY_DAYS = 366
# The largest number a parameter takes, so a result can't overflow to infinity (1e308 USD in rial would).
MAX_NUMBER = 10**15
SECONDS_PER_DAY = 86400


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


class RateStore:
    """The current rates, polled from the feed by one thread and read by the request threads.

    Hold ``lock`` while reading ``rates`` or using ``history``.
    """

    def __init__(self, rates, interval, history=None, notice="", clock=time.time):
        self.rates = rates
        self.interval = interval
        self.history = history
        self.notice = notice
        self.clock = clock
        self.lock = threading.Lock()
        # None until the feed has been read, since the starting rows may be saved prices.
        self.updated_at = None
        self.error = None
        self.failures = 0

    def poll(self):
        """Read the feed once and save the changed prices; a failure is kept in ``error`` for the responses."""
        try:
            live = fetch_live_prices(attempts=1)
        except (OSError, ValueError, KeyError) as error:
            with self.lock:
                self.failures += 1
                self.error = f"feed error, retrying in {self.poll_delay():g}s: {error}"
            return
        with self.lock:
            now = self.clock()
            apply_live_prices(self.rates, live)
            self.updated_at = now
            self.failures = 0
            self.error = record_history(self.history, self.rates, now) if self.history is not None else None

    def poll_delay(self):
        return retry_delay(self.interval, self.failures)

    def is_stale(self, now):
        return self.updated_at is None or now - self.updated_at > self.interval * STALE_POLLS


def unit_param(params):
    unit = params.get("unit", UNIT_NAMES[False]).lower()
    if unit not in UNIT_NAMES.values():
        raise ApiError(BAD_REQUEST, f"unit must be rial or toman, not {unit!r}")
    return unit == UNIT_NAMES[True]


def number_param(params, name, default=None):
    """A number from 0 to MAX_NUMBER from the query string; ``default`` when it's left out (None makes it required)."""
    text = params.get(name)
    if text is None:
        if default is None:
            raise ApiError(BAD_REQUEST, f"missing parameter: {name}")
        return default
    try:
        value = float(text.replace(",", "").rstrip("%"))
    except ValueError:
        raise ApiError(BAD_REQUEST, f"{name} must be a number, not {text!r}") from None
    if not math.isfinite(value) or not 0 <= value <= MAX_NUMBER:
        raise ApiError(BAD_REQUEST, f"{name} must be a number from 0 to {MAX_NUMBER:,}, not {text!r}")
    return value


def unknown_codes(keys):
    return ApiError(NOT_FOUND, f"unknown code: {', '.join(display_code(key).lower() for key in keys)}")


class Api:
    def __init__(self, store):
        self.store = store
        self.routes = {
            ("rates",): self.rates,
            ("rates", None): self.rate,
            ("history", None): self.history,
            ("convert",): self.convert,
            ("jewelry",): self.jewelry,
            ("health",): self.health,
        }

    def handle(self, path, params):
        """(status, payload) for a GET of ``path``, with ``params`` as {name: value} from the query string."""
        parts = [part for part in path.split("/") if part]
        if not parts or parts == [API_PREFIX.strip("/")]:
            return OK, self.index()
        if parts[0] != API_PREFIX.strip("/"):
            return NOT_FOUND, {"error": f"no such endpoint: {path}"}
        name, args = tuple(parts[1:2]), parts[2:]
        route = self.routes.get(name + (None,) * len(args))
        if route is None:
            return NOT_FOUND, {"error": f"no such endpoint: {path}"}
        try:
            with self.store.lock:
                return OK, route(params, *args)
        except ApiError as error:
            return error.status, {"error": error.message}

    def index(self):
        return {"name": "tgju-rates", "version": __version__, "endpoints": list(ENDPOINTS)}

    def freshness(self):
        now = self.store.clock()
        updated = self.store.updated_at
        return {
            "time": iso_time(now),
            "updated": iso_time(updated) if updated is not None else None,
            "stale": self.store.is_stale(now),
            "error": self.store.error,
            "note": self.store.notice or None,
        }

    def by_key(self):
        return {rate["key"]: rate for rate in self.store.rates}

    def prices(self):
        """{key: rial price} of every rate with a price; zero is left out, since converting into it divides by it."""
        prices = {rate["key"]: parse_rial(rate["price"]) for rate in self.store.rates}
        return {key: price for key, price in prices.items() if price}

    def rates(self, params):
        toman = unit_param(params)
        rates = self.store.rates
        if params.get("market"):
            try:
                markets = parse_markets(params["market"])
            except ValueError as error:
                raise ApiError(BAD_REQUEST, str(error)) from None
            rates = [rate for rate in rates if market_of(rate["key"]) in markets]
        if params.get("codes"):
            by_key = {rate["key"]: rate for rate in rates}
            keys = parse_codes(params["codes"])
            unknown = [key for key in keys if key not in by_key]
            if unknown:
                raise unknown_codes(unknown)
            rates = [by_key[key] for key in keys]
        return {**self.freshness(), "unit": UNIT_NAMES[toman], "rates": [rate_record(rate, toman) for rate in rates]}

    def rate(self, params, code):
        toman = unit_param(params)
        key = row_key(code)
        rate = self.by_key().get(key)
        if rate is None:
            raise unknown_codes([key])
        return {**self.freshness(), "unit": UNIT_NAMES[toman], "rate": rate_record(rate, toman)}

    def history(self, params, code):
        toman = unit_param(params)
        days = number_param(params, "days", default=1)
        if not 0 < days <= MAX_HISTORY_DAYS:
            raise ApiError(BAD_REQUEST, f"days must be more than 0 and at most {MAX_HISTORY_DAYS}")
        key = row_key(code)
        if key not in self.by_key():
            raise unknown_codes([key])
        if self.store.history is None:
            raise ApiError(SERVICE_UNAVAILABLE, "history is off (the server runs with --no-record)")
        changes = self.store.history.changes_since(key, self.store.clock() - days * SECONDS_PER_DAY)
        return {**history_record(key, changes, toman=toman), "days": days}

    def convert(self, params):
        amount = number_param(params, "amount")
        if not params.get("from"):
            raise ApiError(BAD_REQUEST, "missing parameter: from")
        conversion = Conversion(amount, unit_of(params["from"]), unit_of(params["to"]) if params.get("to") else "")
        if conversion.source in MONEY_UNITS and not conversion.target:
            raise ApiError(BAD_REQUEST, f"say what to convert {conversion.source} into with 'to'")
        keys = [unit for unit in (conversion.source, conversion.target) if unit and unit not in MONEY_UNITS]
        prices = self.prices()
        error = missing_prices(keys, prices, "")
        if error:
            raise ApiError(NOT_FOUND, error)
        results = convert(conversion, prices)
        return {**self.freshness(), **conversion_record(conversion, results, prices, self.store.notice)}

    def jewelry(self, params):
        weight = number_param(params, "weight")
        if not weight:
            raise ApiError(BAD_REQUEST, "weight must be more than 0 grams")
        piece = Piece(
            weight,
            wage=number_param(params, "wage", default=0.0),
            profit=number_param(params, "profit", default=DEFAULT_PROFIT),
            tax=number_param(params, "tax", default=DEFAULT_TAX),
        )
        gram_price = self.prices().get(GOLD_KEY)
        if gram_price is None:
            raise ApiError(NOT_FOUND, "no price for 18k gold")
        return {**self.freshness(), **quote_record(quote(piece, gram_price), self.store.notice)}

    def health(self, params):
        freshness = self.freshness()
        return {
            "status": "stale" if freshness["stale"] else "ok",
            "version": __version__,
            "rates": len(self.store.rates),
            "history": self.store.history is not None,
            **freshness,
        }
