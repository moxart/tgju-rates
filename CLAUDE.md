# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`tgju-rates` is a standard-library-only Python package (`src/` layout) that shows live currency, gold coin, gold and crypto rates from tgju.org in the terminal. It needs Python 3.9+ (`str.removeprefix`). Keep it dependency-free.

## Commands

```
PYTHONPATH=src python3 -m tgju_rates [--once] [-i 5] [--persian] [--toman] [--json] [--animation roll] [--watch usd,eur] [--alert "usd>2600000"]
PYTHONPATH=src python3 -m tgju_rates --hold usd=1200@2,450,000 [--holdings PATH] [--alert "total>5000000000"]
PYTHONPATH=src python3 -m tgju_rates --history usd [--days 7] [--db PATH] [--chart|--csv]   # saved prices (offline)
PYTHONPATH=src python3 -m tgju_rates --market coin,gold,crypto [--watch usd,emami,btc]
PYTHONPATH=src python3 -m tgju_rates --convert "250 usd eur" | --doctor | --completion bash
PYTHONPATH=src python3 -m unittest discover -s tests        # all tests (offline)
PYTHONPATH=src python3 -m unittest tests.test_screen        # one module
ruff check . && ruff format --check .                       # lint/format (config in pyproject.toml, line length 120)
```

After `pip install .`, the `tgju-rates` console script runs `tgju_rates.cli:main`. CI (`.github/workflows/ci.yml`) runs ruff and then the tests on Python 3.9–3.13.

## Module map (`src/tgju_rates/`)

- `cli.py`: argparse, choosing which markets to load (`--market` plus the markets of watched/alerted/held codes), `load_rates` (falls back to `saved_rates` per failed market), `--watch`/`--alert` validation against the loaded rows, opening the history DB, dispatch to `--completion`/`--doctor`/`--history`/`--convert` (all exit before the live path), SIGTERM routed to `KeyboardInterrupt`.
- `app.py`: `Options` (persian/toman/json/animation), `run_once`, `run_live` (passes a `KeyReader` only when stdin and stdout are TTYs), `saved_rates`, `run_history` (`HISTORY_VIEWS`: list/chart/csv; `--json` wins)/`format_history`/`format_chart`/`history_csv`, and `LiveSession` (poll, then track, then record history, then alerts, then build the frame; `poll_delay` backs off after failures up to `MAX_RETRY_SECONDS`).
- `markets.py`: `FEED_MARKETS` (`coin`/`gold`/`crypto` → `Instrument(key, code, name, persian)`), `INSTRUMENTS`, `KEY_BY_CODE`, `market_of`, `parse_markets`. Imports nothing from the package (currencies.py builds on it).
- `convert.py`: `parse_conversion` → `Conversion`, `convert` (honours `UNIT_SIZE`), `run_convert` (feed prices, else `History.latest`).
- `chart.py`: `resample` (step prices into columns), `render_chart`, `daily_rows`/`daily_summary`.
- `doctor.py`: `run_doctor` and its `check_*` functions, each returning `(status, message)` lines.
- `completion.py`: `completion_script` for bash/zsh (zsh via bashcompinit)/fish, built from `parser._actions` and `known_codes`.
- `holdings.py`: `Holding`, `parse_holding`, `load_holdings` (file at `default_holdings_path`, XDG config dir), `merge_holdings`, `value_holdings` → `Valuation`/`Position`, `TotalTrend` (seeded from history).
- `history.py`: `History` (SQLite, stores a row only when a key's price changes; `latest`, `last_before`), `default_path` (XDG data dir).
- `export.py`: `rates_json` (one line per snapshot, so live `--json` is JSON Lines), `history_json`.
- `source.py`: `CurrencyTableParser`/`parse_page_rates` (HTML), `fetch_live_prices`/`apply_live_prices` (JSON feed), `feed_market_rates`, `load_markets` (per-market results and errors).
- `currencies.py`: `ENGLISH_NAMES` (includes the instruments' names), `CODE_ALIASES`, `UNIT_SIZE` (JPY per 100), `row_key` (instrument codes first), `display_code`, `known_codes`, `parse_rial`, `to_toman`/`rial_to_toman` (rounds toward zero), `parse_change`, `change_in_toman`, `format_amount`.
- `controls.py`: `LiveControls`, the key-driven view state (toman toggle, `SORT_MODES`, filter, animation, pause, quit), `apply` filters/sorts the shown rates.
- `animation.py`: `ANIMATIONS` (`flash`, `glow`, `roll`, `board`, `off`), `cell_style` (colour ramps by age), `rolled` (spinning digits), `ANIMATION_SECONDS`, `FRAME_SECONDS`.
- `keys.py`: `KeyReader` (cbreak mode, `select` on POSIX, `msvcrt` polling on Windows), `split_keys` (keeps escape sequences whole).
- `tracking.py`: `PriceTracker` (previous prices, last up/down move with the price before it, trend deques), `recent_change`, `HIGHLIGHT_SECONDS`, `TREND_POINTS`.
- `alerts.py`: `Alert`, `parse_alert` (raises `ValueError`; cli wraps it in `ArgumentTypeError`), `check_alerts`, `notify`.
- `table.py`: `render_table`, `render_holdings` (the savings panel), `sparkline`, column styles/alignments.
- `screen.py`: `LiveScreen` (in-place diff redraw), `print_frame` (piped output).
- `ansi.py`: escape codes and the colour palette.

## How it works

Data comes from two sources, and both have to agree on the row key (`price_<code>` for currencies):

1. **HTML page** (`PAGE_URL`) is scraped **once** at startup. Each `<tr data-market-row="price_...">` has its cells mapped in order onto `FIELDS` (`name, price, change, low, high, time`). Only the first row per key is kept, because the page lists some currencies twice. This decides which currencies appear and gives their Persian names. If the site's markup changes, this parser is what breaks; see the offline fallback below.
2. **JSON feed** (`FEED_URL`) is polled every interval. `feed["current"][key]` supplies `p` (price), `l`/`h` (low/high), `t` (time), `d`/`dp` (change and change percent), and `dt == "low"` for a negative change. A `?rev=<time_ns>` query string bypasses its 5-minute CDN cache.
3. **Feed markets** (`coin`, `gold`, `crypto`) aren't scraped. Their rows are built from `feed["current"]` and the curated `FEED_MARKETS` list; the row key is the feed's key (`sekee`, `geram18`, `crypto-bitcoin-irr`), and only rial-priced entries belong there. `display_code` shows the instrument's short code (`EMAMI`, `BTC`).

Rates are plain dicts that `apply_live_prices` mutates in place. Prices are rial strings with commas. Feed errors (`OSError`, `ValueError`, `KeyError`) go into the status line and polling continues, with the wait doubling per failure in a row.

Offline fallback: if a market can't be loaded at startup, `load_rates` rebuilds its rows from `History.latest` (change/low/high are `-`), tries one feed fetch to refresh them, prints a note to stderr and passes it to live mode as a `NOTE` line. With nothing saved for it, it exits with the error.

Live output: on a TTY, `LiveScreen` draws on the alternate screen and rewrites only the lines that differ from the previous frame. It does a full redraw after a resize, has line wrap off (so too-wide lines are clipped and row positions stay correct), and cuts a frame taller than the window with a "N more row(s)" note. Piped output gets a full, uncoloured frame per poll.

Table: English names lead, because Persian renders poorly in terminals. A key missing from `ENGLISH_NAMES` shows `-`. `COLUMN_STYLES`, `COLUMN_ALIGNS`, `PRICE_COLUMN` and `CHANGE_COLUMN` in `table.py` must stay in sync with `BASE_HEADER`. The optional TREND (only when a `tracker` is passed, i.e. live mode) and PERSIAN columns are appended in that order, with PERSIAN always last so RTL text doesn't break alignment. Cells end with `END_CELL`, not `RESET`, so they don't clear the row's `STRIPE` background.

Units: everything is stored and compared in rial; toman is a display conversion. With `--toman` the table uses `TOMAN_HEADER` (toman price first, rial second; same column count, so the style tuples still line up), and `--alert` limits are read as toman and multiplied into rial. `alert_argument` only validates syntax; rules are parsed in `cli.run` once `--toman` is known.

Watchlist/alerts: `--watch` only filters what's displayed. Every currency is still polled, so alerts work outside the watchlist. Alert limits are stored in rial. An alert fires once, then re-arms when its condition stops holding (state is the `active` set).

Trends: `PriceTracker.update` appends to a key's deque only when the price differs from the deque's last entry, so the sparkline shows the last N *changes*, not time. Live mode seeds the deques from `History.recent_prices` (`load_trends`). Seeding doesn't touch `previous_prices`, so a restart doesn't flag ▲/▼ moves.

Keys: `LiveSession.run` waits on `keys.read(timeout)` until the next poll instead of sleeping, so a key redraws at once (timeout `None` while paused). The display unit comes from `controls.toman`, not `options.toman`, so `t` affects the table, JSON and alert messages; alert limits were converted to rial at startup and don't change. While the filter is being typed, every key (including `q`) goes into it.

Animations: `render_table` asks `tracker.recent_change(key, now, ANIMATION_SECONDS)` and, only with `color`, restyles the price and secondary-unit cells (and with `roll`/`board` replaces their text with `rolled`, which never changes the width). A flash sets a background, so that cell ends with `END_CELL` plus the row's background (`STRIPE` or `DEFAULT_BACKGROUND`) instead of plain `END_CELL`. `LiveSession.frame` sets `animating`; while it is true `run` waits at most `FRAME_SECONDS` and redraws, and it draws once more after the animation ends so the cell settles. The current style lives in `controls.animation` (`a` cycles it), starting from `--animation`.

Savings: `--hold` and the holdings file use the same `code=amount[@price [toman|rial]]` syntax; a `--hold` replaces the file's entry for that key. A unit-less price is rial in the file (so the file means the same on every run) and follows `--toman` in `--hold` (like `--alert`). Holdings are valued against all rates, not just `--watch`. `Valuation.complete_worth` is `None` while any holding lacks a price; `total` alerts and the TOTAL sparkline use it so a partial total never fires an alert. A `total` alert (`TOTAL_KEY` in `alerts.py`) without holdings exits with an error.

Converter: `--convert` needs only the feed (every currency, coin and crypto is in it), so it skips the page. It opens the history file only if it already exists (`existing_history`), for the fallback. Output labels `price_dollar_rl` as USD.

History: on by default (`--no-record` disables, `--db` overrides the path). Opening failures warn and continue without history; `sqlite3.Error` while recording goes into the status line. `--history` exits before scraping, so it works offline.
