# tgju-rates

Live Iranian rial exchange rates from [tgju.org](https://www.tgju.org/currency) in your terminal.

- Updates in place: only the rows whose prices changed are redrawn, so the screen doesn't flicker.
- Prices in rial and toman, daily change, low and high.
- ▲/▼ markers on prices that just moved, and a sparkline of each currency's recent changes.
- A watchlist, and price alerts with desktop notifications.
- Toman mode (`--toman`) and JSON output (`--json`) for scripts.
- Price history saved to a local SQLite file, so sparklines survive restarts and past prices can be listed.
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
tgju-rates --toman               # prices in toman; --alert limits are read as toman too
tgju-rates --hold usd=1200@2,450,000 --hold eur=300   # what your savings are worth
tgju-rates --alert "total>5,000,000,000"              # alert on your savings' total
tgju-rates --once --json         # one JSON object; live mode with --json prints one per update (JSON Lines)
tgju-rates --history usd         # saved USD prices from the last day
tgju-rates --history eur --days 7 --toman
```

Currency codes are the site's codes in lower case (`eur`, `gbp`, `aed`, ...). `usd` is accepted for the
US dollar. An unknown code prints the list of valid ones.

Alert limits are in **rial**. An alert fires once when its condition becomes true and fires again only
after the condition has stopped holding in between. Fired alerts are listed above the table and sent as a
desktop notification when `notify-send` is available. Alerts work on any currency, including ones not
in `--watch`.

### Your savings

List the currencies you hold, and a panel above the table shows what each is worth now, how much it has
gained since you bought it, and today's move, with a TOTAL row and a sparkline of your total:

```
   YOUR SAVINGS  AMOUNT   WORTH (RIAL)  SINCE BOUGHT    TODAY
   DOLLAR_RL      1,200  3,101,580,000     ▲ +26.6%   ▲ +0.8%
   EUR              300    877,050,000                ▼ -0.5%
   TOTAL                 3,978,630,000     ▲ +26.6%   ▲ +0.5%  ▁▃▂▆█
```

Write each holding as `code=amount`, or `code=amount@price` with the price you paid per unit. Put them in
`~/.config/tgju-rates/holdings.txt` (or `--holdings PATH`), one per line:

```
# code=amount@price paid per unit
usd=1200@2,450,000
eur=300                 # no price: shows worth and today's move, but no gain
gbp=0.5@330,000 toman
```

or pass them with `--hold`, which replaces the file's line for the same currency. Prices in the file are
rial unless you write `toman` after them; `--hold` prices follow `--toman`, like `--alert` limits. SINCE
BOUGHT on the TOTAL row covers only the holdings with a price. `--alert "total>LIMIT"` fires when your
total crosses the limit, and `--json` adds a `holdings` object.

### Keys

In live mode in a terminal, single keys change the view without restarting:

| Key | Does |
| --- | --- |
| `t` | switch between toman and rial |
| `s` | sort: site order, biggest move today, highest price |
| `/` | filter by code or English name as you type; Enter keeps it, Esc clears it |
| `Esc` | clear the filter |
| `p` | pause and resume updates |
| `q` | quit (Ctrl+C works too) |

`t` only changes the display. `--alert` limits stay in the unit they were given in.

Piped output (`tgju-rates > rates.log`) has no colours, ignores keys and appends a full table on every update.

### JSON

`--json` prints numbers instead of formatted text: `price`, `change`, `low` and `high` are integers in
the unit given by `"unit"` (`"rial"`, or `"toman"` with `--toman`), and `change_percent` is a float. Fields
the site didn't fill are `null`. Alerts that fired on that update are listed under `"alerts"`.

```sh
tgju-rates --once --json --watch usd | jq '.rates[0].price'
tgju-rates --json --watch usd,eur > rates.jsonl
```

### History

Every run saves prices to `~/.local/share/tgju-rates/history.db` (or `$XDG_DATA_HOME/tgju-rates/`). A row
is written only when a price changes. Live mode starts its TREND sparklines from this file, and
`--history CODE` lists what was saved (add `--json` for machine-readable output). Use `--db PATH` for a
different file and `--no-record` to not save anything. If the file can't be opened, the program warns and
runs without it.

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
├── history.py     the SQLite price history
├── export.py      JSON output
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
