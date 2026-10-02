"""Currency codes, English names and rial price formatting."""

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
}


def row_key(code):
    """Turn a user-typed code like "eur" or "usd" into the site's row key."""
    code = code.strip().lower()
    return "price_" + CODE_ALIASES.get(code, code)


def display_code(key):
    return key.removeprefix("price_").upper()


def english_name(key):
    return ENGLISH_NAMES.get(key, "-")


def parse_rial(text):
    """Parse a rial amount like "2,584,650"; returns None for anything that isn't a whole number."""
    digits = text.replace(",", "")
    return int(digits) if digits.isdigit() else None


def to_toman(rial_text):
    rial = parse_rial(rial_text)
    return f"{rial // 10:,}" if rial is not None else "-"
