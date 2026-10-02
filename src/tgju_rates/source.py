"""Fetching rates from tgju.org.

The currency page is scraped once for the list of currencies and their Persian names.
Prices are then polled from the JSON feed the site uses for its own live updates.
Both sources key each currency by the same row key, e.g. ``price_eur``.
"""

import json
import time
from html.parser import HTMLParser
from urllib.request import Request, urlopen

PAGE_URL = "https://www.tgju.org/currency"
FEED_URL = "https://call1.tgju.org/ajax.json"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
REQUEST_TIMEOUT = 20

# Cells in each page row, in page order (the last chart-link cell is dropped).
FIELDS = ("name", "price", "change", "low", "high", "time")


class CurrencyTableParser(HTMLParser):
    """Collects every <tr data-market-row="price_..."> row of the currency tables."""

    def __init__(self):
        super().__init__()
        self.rates = []
        self._row = None
        self._cell = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tr" and (attrs.get("data-market-row") or "").startswith("price_"):
            self._row = {"key": attrs["data-market-row"], "cells": []}
        elif self._row is not None and tag in ("th", "td"):
            self._cell = []

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if self._row is None:
            return
        if tag in ("th", "td") and self._cell is not None:
            self._row["cells"].append("".join(self._cell).strip())
            self._cell = None
        elif tag == "tr":
            row = self._row
            self._row = None
            # The page lists some currencies twice (summary + full table); keep the first.
            if len(row["cells"]) >= len(FIELDS) and all(r["key"] != row["key"] for r in self.rates):
                self.rates.append({"key": row["key"], **dict(zip(FIELDS, row["cells"]))})


def fetch(url):
    request = Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "fa,en;q=0.8", "Referer": "https://www.tgju.org/"},
    )
    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_page_rates(html):
    parser = CurrencyTableParser()
    parser.feed(html)
    return parser.rates


def scrape_page_rates():
    return parse_page_rates(fetch(PAGE_URL))


def fetch_live_prices():
    # The feed sits behind a 5-minute CDN cache; a unique query string gets fresh data.
    feed = json.loads(fetch(f"{FEED_URL}?rev={time.time_ns()}"))
    return feed["current"]


def apply_live_prices(rates, live):
    """Update the scraped rates in place from the feed's ``current`` section."""
    for rate in rates:
        item = live.get(rate["key"])
        if not item:
            continue
        rate["price"] = item["p"]
        rate["low"] = item["l"]
        rate["high"] = item["h"]
        rate["time"] = item["t"]
        sign = "-" if item.get("dt") == "low" else ""
        rate["change"] = f"({sign}{item['dp']}%) {sign}{item['d']}"
