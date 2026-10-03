"""Currency codes, English names and rial/toman price formatting."""

import re

from tgju_rates.markets import INSTRUMENTS, KEY_BY_CODE

RIAL_PER_TOMAN = 10
UNIT_NAMES = {False: "rial", True: "toman"}
# A change cell like "(-0.8%) -23,500": percent, then the amount in rial.
CHANGE_PATTERN = re.compile(r"^\((-?[\d.]+)%\)\s*(-?[\d,]+)$")

# The site's key for the US dollar isn't its ISO code, so accept "usd" as well.
CODE_ALIASES = {"usd": "dollar_rl"}

# Persian script renders poorly in most terminal fonts, so the table leads with English names.
# Keyed by the site's row key; a currency the site adds later needs an entry here.
ENGLISH_NAMES = {
    "price_dollar_rl": "US Dollar",
    "price_eur": "Euro",
    "price_aed": "UAE Dirham",
    "price_gbp": "British Pound",
    "price_try": "Turkish Lira",
    "price_chf": "Swiss Franc",
    "price_cny": "Chinese Yuan",
    "price_jpy": "Japanese Yen (100)",
    "price_krw": "South Korean Won",
    "price_cad": "Canadian Dollar",
    "price_aud": "Australian Dollar",
    "price_nzd": "New Zealand Dollar",
    "price_sgd": "Singapore Dollar",
    "price_inr": "Indian Rupee",
    "price_pkr": "Pakistani Rupee",
    "price_iqd": "Iraqi Dinar",
    "price_syp": "Syrian Pound",
    "price_afn": "Afghan Afghani",
    "price_dkk": "Danish Krone",
    "price_sek": "Swedish Krona",
    "price_nok": "Norwegian Krone",
    "price_sar": "Saudi Riyal",
    "price_qar": "Qatari Riyal",
    "price_omr": "Omani Rial",
    "price_kwd": "Kuwaiti Dinar",
    "price_bhd": "Bahraini Dinar",
    "price_myr": "Malaysian Ringgit",
    "price_thb": "Thai Baht",
    "price_hkd": "Hong Kong Dollar",
    "price_rub": "Russian Ruble",
    "price_azn": "Azerbaijani Manat",
    "price_amd": "Armenian Dram",
    "price_gel": "Georgian Lari",
    "price_kgs": "Kyrgyzstani Som",
    "price_tjs": "Tajikistani Somoni",
    "price_tmt": "Turkmenistani Manat",
    **{item.key: item.name for item in INSTRUMENTS.values()},
}
# The site prices a few currencies per 100 units; the converter divides by this.
UNIT_SIZE = {"price_jpy": 100}


def row_key(code):
    """Turn a user-typed code like "eur", "usd" or "emami" into the site's row key."""
    code = code.strip().lower()
    if code in KEY_BY_CODE:
        return KEY_BY_CODE[code]
    return "price_" + CODE_ALIASES.get(code, code)


def display_code(key):
    if key in INSTRUMENTS:
        return INSTRUMENTS[key].code.upper()
    return key.removeprefix("price_").upper()


def known_codes():
    """Every code this program knows without asking the site, for completion and error messages."""
    codes = {display_code(key).lower() for key in ENGLISH_NAMES}
    return sorted(codes - {CODE_ALIASES["usd"]} | set(CODE_ALIASES))


def english_name(key):
    return ENGLISH_NAMES.get(key, "-")


def parse_rial(text):
    """Parse a rial amount like "2,584,650"; returns None for anything that isn't a whole number."""
    digits = text.replace(",", "")
    return int(digits) if digits.isdigit() else None


def rial_to_toman(rial):
    """Convert a whole rial amount, rounding toward zero so a fall and a rise of the same size match."""
    toman = abs(rial) // RIAL_PER_TOMAN
    return -toman if rial < 0 else toman


def to_toman(rial_text):
    rial = parse_rial(rial_text)
    return f"{rial_to_toman(rial):,}" if rial is not None else "-"


def format_amount(rial, toman=False):
    """Format a rial amount as "2,584,650 rial", or "258,465 toman" with ``toman``."""
    amount = rial_to_toman(rial) if toman else rial
    return f"{amount:,} {UNIT_NAMES[toman]}"


def parse_change(text):
    """Parse a change cell into (percent, rial amount); returns None if it isn't in the usual form."""
    match = CHANGE_PATTERN.match(text.strip())
    if not match:
        return None
    percent, amount = match.groups()
    try:
        return float(percent), int(amount.replace(",", ""))
    except ValueError:
        return None


def change_in_toman(text):
    """Rewrite a change cell's amount in toman; anything unparseable is left as it is."""
    parsed = parse_change(text)
    if parsed is None:
        return text
    percent, amount = parsed
    return f"({percent:g}%) {rial_to_toman(amount):,}"
