# tgju-rates

Live Iranian rial exchange rates from [tgju.org](https://www.tgju.org/currency) in your terminal.

- Updates in place: only the rows whose prices changed are redrawn, so the screen doesn't flicker.
- Prices in rial and toman, daily change, low and high.
- ▲/▼ markers on prices that just moved, and a sparkline of each currency's recent changes.
- A watchlist, and price alerts with desktop notifications.
- No dependencies. Only the Python standard library is used.

```
tgju.org live rates   updated 14:24:19   every 10s   connected
▲/▼ marks prices that moved in the last 60s.  TREND shows the last 12 price changes.  Ctrl+C to quit.

   CODE       NAME           PRICE (RIAL)    TOMAN  CHANGE              LOW       HIGH  TREND
-------------------------------------------------------------------------------------------------
 ▲ DOLLAR_RL  US Dollar         2,584,650  258,465  (0.4%) 10,050  2,546,600  2,585,200  ▁▃▅█
   EUR        Euro              2,923,500  292,350  (0%) 0         2,885,300  2,926,400
   GBP        British Pound     3,412,800  341,280  (-0.2%) -6,900 3,401,000  3,420,500  █▆▃
```

## Installation

Requires Python 3.9 or newer.

```sh
git clone https://github.com/<your-username>/tgju-rates.git
cd tgju-rates
pip install .
```

You can also run it from the source tree without installing: `PYTHONPATH=src python3 -m tgju_rates`.

## Usage

```sh
tgju-rates                       # live, refresh every 10 seconds
tgju-rates -i 5                  # refresh every 5 seconds (minimum 3)
tgju-rates --once                # print the table once and exit
tgju-rates --persian             # add a column with the Persian names
tgju-rates --watch usd,eur,gbp   # show only these currencies, in this order
tgju-rates --alert "usd>2600000" --alert "eur<=2,850,000"
```

Currency codes are the site's codes in lower case (`eur`, `gbp`, `aed`, ...). `usd` is accepted for the
US dollar. An unknown code prints the list of valid ones.

Alert limits are in **rial**. An alert fires once when its condition becomes true and fires again only
after the condition has stopped holding in between. Fired alerts are listed above the table and sent as a
desktop notification when `notify-send` is available. Alerts work on any currency, including ones not
in `--watch`.

Piped output (`tgju-rates > rates.log`) has no colours and appends a full table on every update.

## How it works

1. At startup, the [currency page](https://www.tgju.org/currency) is scraped once to find which
   currencies to show and their Persian names.
2. While running, prices are polled from `https://call1.tgju.org/ajax.json`, the feed the site uses for
   its own live updates. A unique query string gets around its 5-minute CDN cache.

If tgju.org changes its page markup, the scraper is the part that breaks. The program then exits with
"No rates found".

## Project layout

```
src/tgju_rates/
├── cli.py         argument parsing and the entry point
├── app.py         --once mode and the live polling loop
├── source.py      scraping the page and reading the JSON feed
├── currencies.py  currency codes, English names, rial/toman formatting
├── tracking.py    price moves between polls and trend history
├── alerts.py      alert rules and desktop notifications
├── table.py       rendering the table, sparklines and colours
├── screen.py      flicker-free in-place terminal updates
└── ansi.py        terminal escape codes and the colour palette
tests/             unit tests (offline, no network needed)
```

## Development

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install -e . ruff
python -m unittest discover -s tests   # tests
ruff check . && ruff format --check .  # lint and formatting
```

A currency the site adds later shows `-` as its name until it gets an entry in `ENGLISH_NAMES` in
`currencies.py`.

## Disclaimer

This is an unofficial tool and is not affiliated with tgju.org. All data belongs to tgju.org. Please
keep the refresh interval reasonable.

## License

[MIT](LICENSE)
