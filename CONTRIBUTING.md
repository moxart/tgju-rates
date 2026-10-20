# Contributing

Bug reports and pull requests are welcome.

## Reporting a bug

Run `tgju-rates --doctor` first and include its output. It shows whether tgju.org's page and feed
still look the way the program expects, which is the most common reason something stops working.
For a crash, run the same command again with `--debug` and include the traceback.

## Development setup

```sh
git clone https://github.com/moxart/tgju-rates.git
cd tgju-rates
python3 -m venv .venv && . .venv/bin/activate
pip install -e . ruff
```

Run it from the source tree with `tgju-rates`, or without installing with `PYTHONPATH=src python3 -m tgju_rates`.

## Before you open a pull request

```sh
python -m unittest discover -s tests   # offline; no network needed
ruff check . && ruff format --check .
```

CI runs both on Python 3.9 to 3.13.

Some rules the code follows:

- **Standard library only.** The program has no dependencies, and that should stay true.
- **Python 3.9.** Don't use syntax or library features from later versions (`match`, `X | Y` types,
  `tomllib`, ...).
- **Tests stay offline.** Mock `fetch_live_prices`/`scrape_page_rates` instead of calling the site.
- **Prices are rial internally.** Toman is a display conversion only.
- `CLAUDE.md` describes how the modules fit together, and is worth reading before a larger change.

Add a line under `[Unreleased]` in `CHANGELOG.md` for anything a user would notice.

## Releasing

1. Move the `[Unreleased]` entries in `CHANGELOG.md` under a new version heading.
2. Set `__version__` in `src/tgju_rates/__init__.py` to the same version.
3. Commit, merge to `main`, then tag `main` and push the tag:
   `git switch main && git pull && git tag v0.2.0 && git push origin v0.2.0`.

The workflow refuses a tag whose commit isn't on `main`.

The release workflow (`.github/workflows/release.yml`) builds the wheel and source archive, checks that
the tag matches `__version__`, publishes both to [PyPI](https://pypi.org/project/tgju-rates/) through
trusted publishing, then attaches them to a GitHub release. A version can't be re-uploaded to PyPI, so
a bad release needs a new version number.

One-time PyPI setup (pypi.org → Your projects → Publishing → add a pending publisher):

| Field | Value |
| --- | --- |
| PyPI project name | `tgju-rates` |
| Owner | `moxart` |
| Repository name | `tgju-rates` |
| Workflow name | `release.yml` |
| Environment name | `pypi` |

Also create an environment called `pypi` under the repository's Settings → Environments (adding a
required reviewer there gives a manual approval step before each upload).
