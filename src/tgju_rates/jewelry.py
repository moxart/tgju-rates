"""``--jewelry "12.5g wage 18%"``: what a piece of 18k gold jewelry should cost at today's gold price.

It follows the formula Iranian gold shops use:

    gold    = weight × price of one gram of 18k gold
    wage    = gold × making charge (اجرت ساخت)
    profit  = (gold + wage) × the seller's profit
    tax     = (wage + profit) × VAT; the gold itself isn't taxed
    total   = gold + wage + profit + tax
"""

import json
import re
from dataclasses import dataclass

from tgju_rates.convert import missing_prices, prices_for
from tgju_rates.currencies import RIAL_PER_TOMAN, UNIT_NAMES, rial_to_toman

GOLD_KEY = "geram18"
DEFAULT_PROFIT = 7.0
# Iran's VAT rate since 1403 (2024); "tax N%" overrides it if it changes.
DEFAULT_TAX = 10.0
SETTINGS = ("wage", "profit", "tax")
WEIGHT_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)\s*(?:g|gr|gram|grams)?$", re.IGNORECASE)
PERCENT_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)%?$")
WEIGHT_UNITS = {"g", "gr", "gram", "grams"}
EXAMPLE = '"12.5g wage 18%" or "8 grams wage 20% profit 5%"'


@dataclass(frozen=True)
class Piece:
    weight: float  # grams
    wage: float = 0.0  # percents
    profit: float = DEFAULT_PROFIT
    tax: float = DEFAULT_TAX


@dataclass(frozen=True)
class Quote:
    piece: Piece
    gram_price: int  # rial
    gold: int
    wage: int
    profit: int
    tax: int

    @property
    def total(self):
        return self.gold + self.wage + self.profit + self.tax


def parse_piece(text):
    """Parse ``WEIGHT[g] [wage N%] [profit N%] [tax N%]``. Raises ValueError."""
    words = text.split()
    # "12.5 g" and "12.5g" both work: glue a separate unit onto the number.
    if len(words) > 1 and words[1].lower() in WEIGHT_UNITS:
        words[:2] = [words[0] + words[1]]
    match = WEIGHT_PATTERN.match(words[0]) if words else None
    if not match or float(match.group(1)) <= 0:
        raise ValueError(f"{text!r} doesn't start with a weight in grams; try {EXAMPLE}")
    settings = {}
    pairs = words[1:]
    if len(pairs) % 2:
        raise ValueError(f"{text!r}: {pairs[-1]!r} needs a percent after it; try {EXAMPLE}")
    for name, value in zip(pairs[::2], pairs[1::2]):
        name = name.lower()
        percent = PERCENT_PATTERN.match(value)
        if name not in SETTINGS:
            raise ValueError(f"{text!r}: unknown setting {name!r}; use {', '.join(SETTINGS)}")
        if not percent:
            raise ValueError(f"{text!r}: {value!r} isn't a percent for {name}")
        settings[name] = float(percent.group(1))
    return Piece(float(match.group(1)), **settings)


def whole_toman(rial):
    return round(rial / RIAL_PER_TOMAN) * RIAL_PER_TOMAN


def quote(piece, gram_price):
    """Each part of the price, in rial rounded to a whole toman, so the parts add up in either unit."""
    gold = piece.weight * gram_price
    wage = gold * piece.wage / 100
    profit = (gold + wage) * piece.profit / 100
    tax = (wage + profit) * piece.tax / 100
    return Quote(piece, gram_price, *(whole_toman(part) for part in (gold, wage, profit, tax)))


def percent(value):
    return f"{value:g}%"


def format_quote(result, toman=False, note=""):
    piece = result.piece
    units = [UNIT_NAMES[toman], UNIT_NAMES[not toman]]

    def amounts(rial):
        values = [rial_to_toman(rial), rial] if toman else [rial, rial_to_toman(rial)]
        return [f"{value:,}" for value in values]

    rows = [
        ("Gold", result.gold),
        (f"Making charge {percent(piece.wage)}", result.wage),
        (f"Seller's profit {percent(piece.profit)}", result.profit),
        (f"VAT {percent(piece.tax)} on charge and profit", result.tax),
    ]
    table = [(label, *amounts(rial)) for label, rial in rows]
    total = ("Total", *amounts(result.total))
    header = ("", *(unit.upper() for unit in units))
    widths = [max(len(row[i]) for row in (header, *table, total)) for i in range(3)]

    def line(row):
        return f"  {row[0]:<{widths[0]}}  {row[1]:>{widths[1]}}  {row[2]:>{widths[2]}}".rstrip()

    gram = amounts(result.gram_price)[0]
    lines = [f"{piece.weight:g} g of 18k gold at {gram} {units[0]} per gram", "", line(header)]
    lines += [line(row) for row in table]
    lines += ["  " + "-" * (sum(widths) + 4), line(total)]
    if note:
        lines += ["", note]
    return "\n".join(lines)


def quote_record(result, note=""):
    piece = result.piece
    return {
        "weight_grams": piece.weight,
        "gram_price_rial": result.gram_price,
        "percents": {"wage": piece.wage, "profit": piece.profit, "tax": piece.tax},
        "parts_rial": {"gold": result.gold, "wage": result.wage, "profit": result.profit, "tax": result.tax},
        "total_rial": result.total,
        "total_toman": rial_to_toman(result.total),
        "note": note or None,
    }


def quote_json(result, note=""):
    return json.dumps(quote_record(result, note))


def run_jewelry(text, history=None, toman=False, as_json=False):
    """Print the price breakdown; returns an error message instead when there's no gold price."""
    piece = parse_piece(text)
    prices, note = prices_for([GOLD_KEY], history)
    error = missing_prices([GOLD_KEY], prices, note)
    if error:
        return error
    result = quote(piece, prices[GOLD_KEY])
    print(quote_json(result, note) if as_json else format_quote(result, toman=toman, note=note))
    return None
