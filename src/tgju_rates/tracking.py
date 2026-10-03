"""Price movement between polls: up/down highlights and the trend history."""

from collections import deque

from tgju_rates.currencies import parse_rial

# How long a changed price stays highlighted.
HIGHLIGHT_SECONDS = 60
# Live mode keeps this many recent price changes per currency for the TREND sparkline.
TREND_POINTS = 12


class PriceTracker:
    """Remembers the previous poll's prices, the latest move per currency, and recent price changes."""

    def __init__(self):
        self.previous_prices = {}
        # key -> ("up" | "down", timestamp of the move, price before the move)
        self.last_moves = {}
        # key -> deque of the last TREND_POINTS distinct prices
        self.trends = {}

    def load_trends(self, trends):
        """Start the sparklines from saved history ({key: [prices, oldest first]})."""
        for key, prices in trends.items():
            if prices:
                self.trends[key] = deque(prices, maxlen=TREND_POINTS)

    def update(self, rates, now):
        for rate in rates:
            key = rate["key"]
            old, new = self.previous_prices.get(key), parse_rial(rate["price"])
            if old is not None and new is not None and new != old:
                self.last_moves[key] = ("up" if new > old else "down", now, old)
            # Only changes are recorded, so the sparkline shows movement rather than a long flat line.
            trend = self.trends.get(key)
            if new is not None and (not trend or trend[-1] != new):
                self.trends.setdefault(key, deque(maxlen=TREND_POINTS)).append(new)
            self.previous_prices[key] = new

    def recent_move(self, key, now):
        """Return "up" or "down" if the price moved within HIGHLIGHT_SECONDS, else None."""
        change = self.recent_change(key, now, HIGHLIGHT_SECONDS)
        return change[0] if change else None

    def recent_change(self, key, now, seconds):
        """Return (direction, price before, seconds since) for a move within ``seconds``, else None."""
        move = self.last_moves.get(key)
        if move and now - move[1] < seconds:
            return move[0], move[2], now - move[1]
        return None
