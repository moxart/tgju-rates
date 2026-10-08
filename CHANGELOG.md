# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Settings file (`~/.config/tgju-rates/config.ini`, or `--config PATH`) with defaults for the display,
  live-mode, alert and history options. `--doctor` checks it.
- `--no-toman`, `--no-persian`, `--no-jalali` and `--no-dashboard`, to turn off a default set in the
  settings file.
- `--color auto|always|never`. `auto` follows `NO_COLOR`, `FORCE_COLOR` and `TERM=dumb`.
- Live mode: a title bar with the connection state (LIVE, OFFLINE, PAUSED), a key bar pinned to the
  bottom row that shows the keys for the current view, and a `?` help screen.
- `m` in live mode mutes alerts (no notifications, ALERT lines cleared) until pressed again, and
  `--no-alerts` ignores every alert for one run, including those in the settings file.
- `--debug`, which shows the traceback of an unexpected error. Without it the error is one line with
  a link for reporting it.
- The `--once` header shows when the prices were fetched.

### Changed

- Requests ask for gzip, so each poll of the feed downloads about 26 KB instead of 176 KB.
- A request that fails on the network at startup is retried once before falling back to saved prices.
- The CHANGE column is signed and leads with the amount: `+4,000 (+0.15%)` instead of `(0.15%) 4,000`.
- Rows no longer show ▲/▼ right after startup, which came from the page being a few minutes behind
  the feed.
- `--help` groups the options and starts with a short synopsis and examples.
- Exit statuses: 0 on success, 1 on an error, 2 on a usage error, 130 when interrupted. Piping into a
  program that stops reading (`| head`) exits quietly.

### Fixed

- Piped live output with `--color always` or `FORCE_COLOR` no longer prints about 20 extra frames each
  time a price changes; animations only play on the live screen.
- An arrow key read together with a typed key (e.g. while holding it) is no longer split into Esc and
  text, which cleared the filter or typed `[A` into it.
- `--convert` and `--jewelry` report a zero price as missing instead of failing with a division by zero.

## [0.1.0] - 2026-10-04

### Added

- Live rates from tgju.org with in-place, flicker-free updates, ▲/▼ markers, TREND sparklines and
  price-change animations (`flash`, `glow`, `roll`, `board`).
- Gold coins, gold and silver, and crypto (`--market`), and a `--dashboard` with one panel per market.
- Watchlist, price alerts with desktop notifications, and a savings panel (`--hold`, holdings file).
- Toman mode, JSON output, Persian names, and Jalali dates.
- Price history in SQLite with `--history`, `--chart` and `--csv`.
- `--convert`, the `--jewelry` calculator, `--doctor` and shell completion.
- Keys in live mode: select and open details, toman/rial, sort, filter, converter, animation, pause.

[Unreleased]: https://github.com/moxart/tgju-rates/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/moxart/tgju-rates/releases/tag/v0.1.0
