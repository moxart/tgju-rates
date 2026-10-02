# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`tgju-rates` is a standard-library-only Python package (`src/` layout) that shows live currency rates from tgju.org in the terminal. It needs Python 3.9+ (`str.removeprefix`). Keep it dependency-free.

## Commands

```
PYTHONPATH=src python3 -m tgju_rates [--once] [-i 5] [--persian] [--watch usd,eur] [--alert "usd>2600000"]
PYTHONPATH=src python3 -m unittest discover -s tests        # all tests (offline)
PYTHONPATH=src python3 -m unittest tests.test_screen        # one module
ruff check . && ruff format --check .                       # lint/format (config in pyproject.toml, line length 120)
```

After `pip install .`, the `tgju-rates` console script runs `tgju_rates.cli:main`. CI (`.github/workflows/ci.yml`) runs ruff and then the tests on Python 3.9–3.13.

## Module map (`src/tgju_rates/`)

- `cli.py`: argparse, `--watch`/`--alert` validation against the scraped page, SIGTERM routed to `KeyboardInterrupt`.
- `app.py`: `run_once`, `run_live`, and `LiveSession` (poll, then track, then alerts, then build the frame).
- `source.py`: `CurrencyTableParser`/`parse_page_rates` (HTML), `fetch_live_prices`/`apply_live_prices` (JSON feed).
- `currencies.py`: `ENGLISH_NAMES`, `CODE_ALIASES`, `row_key`, `display_code`, `parse_rial`, `to_toman`.
- `tracking.py`: `PriceTracker` (previous prices, last up/down move, trend deques), `HIGHLIGHT_SECONDS`, `TREND_POINTS`.
- `alerts.py`: `Alert`, `parse_alert` (raises `ValueError`; cli wraps it in `ArgumentTypeError`), `check_alerts`, `notify`.
- `table.py`: `render_table`, `sparkline`, column styles/alignments.
- `screen.py`: `LiveScreen` (in-place diff redraw), `print_frame` (piped output).
- `ansi.py`: escape codes and the colour palette.

## How it works

Data comes from two sources, and both have to agree on the row key (`price_<code>`):

1. **HTML page** (`PAGE_URL`) is scraped **once** at startup. Each `<tr data-market-row="price_...">` has its cells mapped in order onto `FIELDS` (`name, price, change, low, high, time`). Only the first row per key is kept, because the page lists some currencies twice. This decides which currencies appear and gives their Persian names. If the site's markup changes, this parser is what breaks, and `main()` exits with "No rates found".
2. **JSON feed** (`FEED_URL`) is polled every interval. `feed["current"][key]` supplies `p` (price), `l`/`h` (low/high), `t` (time), `d`/`dp` (change and change percent), and `dt == "low"` for a negative change. A `?rev=<time_ns>` query string bypasses its 5-minute CDN cache.

Rates are plain dicts that `apply_live_prices` mutates in place. Prices are rial strings with commas. Feed errors (`OSError`, `ValueError`, `KeyError`) go into the status line and polling continues.

Live output: on a TTY, `LiveScreen` draws on the alternate screen and rewrites only the lines that differ from the previous frame. It does a full redraw after a resize, has line wrap off (so too-wide lines are clipped and row positions stay correct), and cuts a frame taller than the window with a "N more row(s)" note. Piped output gets a full, uncoloured frame per poll.

Table: English names lead, because Persian renders poorly in terminals. A key missing from `ENGLISH_NAMES` shows `-`. `COLUMN_STYLES`, `COLUMN_ALIGNS`, `PRICE_COLUMN` and `CHANGE_COLUMN` in `table.py` must stay in sync with `BASE_HEADER`. The optional TREND (only when a `tracker` is passed, i.e. live mode) and PERSIAN columns are appended in that order, with PERSIAN always last so RTL text doesn't break alignment. Cells end with `END_CELL`, not `RESET`, so they don't clear the row's `STRIPE` background.

Watchlist/alerts: `--watch` only filters what's displayed. Every currency is still polled, so alerts work outside the watchlist. Alert limits are in rial. An alert fires once, then re-arms when its condition stops holding (state is the `active` set).

Trends: `PriceTracker.update` appends to a key's deque only when the price changed, so the sparkline shows the last N *changes*, not time. The history lives only in memory.
