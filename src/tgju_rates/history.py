"""Price history in a local SQLite file, so trends survive restarts and past prices can be listed.

Only changes are stored: a row is written when a currency's price differs from the last one saved.
"""

import os
import sqlite3
from pathlib import Path

from tgju_rates.currencies import parse_rial

SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    key TEXT NOT NULL,
    time REAL NOT NULL,  -- Unix timestamp of the poll that saw this price
    price INTEGER NOT NULL  -- rial
);
CREATE INDEX IF NOT EXISTS prices_key_time ON prices (key, time);
"""
# Seconds to wait for another tgju-rates process that is writing at the same moment.
LOCK_TIMEOUT = 5


def default_path():
    data_home = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(data_home) / "tgju-rates" / "history.db"


class History:
    def __init__(self, connection):
        self._db = connection
        self._db.executescript(SCHEMA)
        # SQLite returns the row holding MAX(time) for the bare "price" column.
        self._last_saved = {
            key: price for key, price, _ in self._db.execute("SELECT key, price, MAX(time) FROM prices GROUP BY key")
        }

    @classmethod
    def open(cls, path, threads=False):
        """Open (creating if needed) the history file. Raises OSError or sqlite3.Error.

        With ``threads``, other threads may use it too; the caller makes sure they take turns.
        """
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        return cls(sqlite3.connect(str(path), timeout=LOCK_TIMEOUT, check_same_thread=not threads))

    def close(self):
        self._db.close()

    def record(self, rates, now):
        """Save the prices that changed since they were last saved."""
        rows = []
        for rate in rates:
            price = parse_rial(rate["price"])
            if price is not None and price != self._last_saved.get(rate["key"]):
                rows.append((rate["key"], now, price))
        if not rows:
            return
        with self._db:
            self._db.executemany("INSERT INTO prices (key, time, price) VALUES (?, ?, ?)", rows)
        self._last_saved.update((key, price) for key, _, price in rows)

    def recent_prices(self, key, limit):
        """The last ``limit`` saved prices for a currency, oldest first."""
        rows = self._db.execute(
            "SELECT price FROM prices WHERE key = ? ORDER BY time DESC LIMIT ?", (key, limit)
        ).fetchall()
        return [price for (price,) in reversed(rows)]

    def changes_since(self, key, start):
        """(time, price) pairs saved for a currency at or after ``start``, oldest first."""
        return self._db.execute(
            "SELECT time, price FROM prices WHERE key = ? AND time >= ? ORDER BY time", (key, start)
        ).fetchall()

    def last_before(self, key, start):
        """The (time, price) in effect just before ``start``, or None if nothing was saved earlier."""
        return self._db.execute(
            "SELECT time, price FROM prices WHERE key = ? AND time < ? ORDER BY time DESC LIMIT 1", (key, start)
        ).fetchone()

    def latest(self):
        """{key: (time, price)} with the last saved price of every key, for when tgju.org can't be reached."""
        rows = self._db.execute("SELECT key, MAX(time), price FROM prices GROUP BY key")
        return {key: (time, price) for key, time, price in rows}
