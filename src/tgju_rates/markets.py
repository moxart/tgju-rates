"""The markets: currencies from the scraped page, and gold coins, gold and crypto straight from the feed.

The currency page decides which currencies exist. The other markets aren't scraped: the feed's
``current`` section already carries them, so each is listed here with the feed's key, the code you
type for it, and its English and Persian names. Only rial-priced entries belong here (the feed also
has dollar-priced ones, such as the gold ounce, that the rial/toman columns can't show).
"""

from typing import NamedTuple

CURRENCY = "currency"


class Instrument(NamedTuple):
    key: str  # the feed's key
    code: str  # what you type, e.g. in --watch; must be a single word
    name: str
    persian: str


FEED_MARKETS = {
    "coin": (
        Instrument("sekee", "emami", "Emami Gold Coin", "سکه امامی"),
        Instrument("sekeb", "bahar", "Bahar Azadi Gold Coin", "سکه بهار آزادی"),
        Instrument("nim", "nim", "Half Gold Coin", "نیم سکه"),
        Instrument("rob", "rob", "Quarter Gold Coin", "ربع سکه"),
        Instrument("gerami", "gerami", "Gram Gold Coin", "سکه گرمی"),
    ),
    "gold": (
        Instrument("geram18", "gold18", "18k Gold (gram)", "طلای 18 عیار / 750"),
        Instrument("geram24", "gold24", "24k Gold (gram)", "طلای ۲۴ عیار"),
        Instrument("mesghal", "mesghal", "Gold Mithqal", "مثقال طلا"),
        Instrument("gold_mini_size", "usedgold", "Used 18k Gold (gram)", "طلای دست دوم"),
        Instrument("silver_999", "silver", "Silver 999 (gram)", "گرم نقره ۹۹۹"),
        Instrument("silver_925", "silver925", "Silver 925 (gram)", "گرم نقره ۹۲۵"),
    ),
    "crypto": (
        Instrument("crypto-bitcoin-irr", "btc", "Bitcoin", "بیت کوین"),
        Instrument("crypto-ethereum-irr", "eth", "Ethereum", "اتریوم"),
        Instrument("crypto-tether-irr", "usdt", "Tether", "تتر"),
        Instrument("crypto-binance-coin-irr", "bnb", "BNB", "بایننس کوین"),
        Instrument("crypto-ripple-irr", "xrp", "XRP", "ریپل"),
        Instrument("crypto-usd-coin-irr", "usdc", "USD Coin", "یو اس دی کوین"),
        Instrument("crypto-solana-irr", "sol", "Solana", "سولانا"),
        Instrument("crypto-tron-irr", "trx", "TRON", "ترون"),
        Instrument("crypto-dogecoin-irr", "doge", "Dogecoin", "دوج کوین"),
        Instrument("crypto-cardano-irr", "ada", "Cardano", "کاردانو"),
        Instrument("crypto-toncoin-irr", "ton", "Toncoin", "تون‌کوین"),
        Instrument("crypto-chainlink-irr", "link", "Chainlink", "چین لینک"),
        Instrument("crypto-stellar-irr", "xlm", "Stellar", "استلار"),
        Instrument("crypto-litecoin-irr", "ltc", "Litecoin", "لایت کوین"),
        Instrument("crypto-bitcoin-cash-irr", "bch", "Bitcoin Cash", "بیت کوین کش"),
        Instrument("crypto-avalanche-irr", "avax", "Avalanche", "آوالانچ"),
        Instrument("crypto-polkadot-irr", "dot", "Polkadot", "پولکا دات"),
        Instrument("crypto-monero-irr", "xmr", "Monero", "مونرو"),
        Instrument("crypto-shiba-inu-irr", "shib", "Shiba Inu", "شیبا اینو"),
    ),
}
MARKETS = (CURRENCY, *FEED_MARKETS)
ALL_MARKETS = "all"

INSTRUMENTS = {item.key: item for items in FEED_MARKETS.values() for item in items}
# Both the short code and the feed's own key are accepted wherever a code is typed.
KEY_BY_CODE = {**{item.code: item.key for item in INSTRUMENTS.values()}, **{key: key for key in INSTRUMENTS}}
MARKET_BY_KEY = {item.key: market for market, items in FEED_MARKETS.items() for item in items}


def market_of(key):
    """The market a row key belongs to; anything not listed above is a currency."""
    return MARKET_BY_KEY.get(key, CURRENCY)


def parse_markets(text):
    """Turn "coin,gold" or "all" into market names in the given order. Raises ValueError."""
    names = list(dict.fromkeys(name.strip().lower() for name in text.split(",") if name.strip()))
    if ALL_MARKETS in names:
        return list(MARKETS)
    unknown = [name for name in names if name not in MARKETS]
    if unknown or not names:
        raise ValueError(f"unknown market {', '.join(unknown) or repr(text)}; choose from {', '.join(MARKETS)} or all")
    return names
