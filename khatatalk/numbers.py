"""Urdu and Roman-Urdu number normalisation helper.

Parses Urdu script digits (۰-۹), Roman-Urdu number words ("char sau", "paanch sau",
"dedh sau", "hazaar"), and standard numeric digits to integers.
Used to cross-check LLM-extracted amounts.
"""

from __future__ import annotations

import re
from typing import Optional

# Mapping of Urdu numerals to standard digits
URDU_DIGITS_MAP = {
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
    "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
}

# Base number words
BASE_NUMBERS = {
    # 1 - 10
    "ek": 1, "aik": 1, "yak": 1, "ایک": 1,
    "do": 2, "دو": 2,
    "teen": 3, "tin": 3, "تین": 3,
    "char": 4, "chaar": 4, "چار": 4,
    "paanch": 5, "panch": 5, "پانچ": 5,
    "chhe": 6, "che": 6, "cha": 6, "chha": 6, "چھ": 6,
    "saat": 7, "سات": 7,
    "aath": 8, "ath": 8, "آٹھ": 8, "اٹھ": 8,
    "nau": 9, "no": 9, "نو": 9,
    "das": 10, "dus": 10, "دس": 10,
    # 11 - 20
    "gyarah": 11, "giarah": 11, "گیارہ": 11,
    "barah": 12, "بارہ": 12,
    "terah": 13, "تیرہ": 13,
    "chaudah": 14, "chodah": 14, "چودہ": 14,
    "pandrah": 15, "پندرہ": 15,
    "solah": 16, "سولہ": 16,
    "satrah": 17, "سترہ": 17,
    "atharah": 18, "itharah": 18, "اٹھارہ": 18,
    "unnees": 19, "unis": 19, "انیس": 19,
    "bees": 20, "bis": 20, "بیس": 20,
    # 21 - 99 multiples of 10 & common
    "pachees": 25, "pachis": 25, "پچیس": 25,
    "tees": 30, "tis": 30, "تیس": 30,
    "paintees": 35, "پینتیس": 35,
    "chalis": 40, "chalees": 40, "چالیس": 40,
    "paintalees": 45, "پینتالیس": 45,
    "pachaas": 50, "pachas": 50, "پچاس": 50,
    "saath": 60, "sath": 60, "ساٹھ": 60,
    "sattar": 70, "ستر": 70,
    "assi": 80, "اسی": 80,
    "nabbe": 90, "naway": 90, "نود": 90, "نوے": 90,
}

# Multipliers & fractions
MULTIPLIERS = {
    "sau": 100, "so": 100, "سو": 100,
    "hazaar": 1000, "hazar": 1000, "hazār": 1000, "ہزار": 1000,
    "lakh": 100000, "lac": 100000, "laakh": 100000, "لاکھ": 100000,
    "karor": 10000000, "crore": 10000000, "کروڑ": 10000000,
}

SPECIAL_COMBINATIONS = {
    # 150
    "dedh sau": 150, "dedh so": 150, "ڈیڑھ سو": 150, "dedhso": 150, "dedhsau": 150,
    # 250
    "dhaai sau": 250, "dhai sau": 250, "dhai so": 250, "dhaai so": 250, "ڈھائی سو": 250,
    # 1500
    "dedh hazaar": 1500, "dedh hazar": 1500, "ڈیڑھ ہزار": 1500,
    # 2500
    "dhai hazaar": 2500, "dhai hazar": 2500, "ڈھائی ہزار": 2500,
    # 3500
    "sadhe teen hazaar": 3500, "sadhe tin hazar": 3500, "ساڑھے تین ہزار": 3500,
}


def convert_urdu_digits(text: str) -> str:
    """Converts Urdu / Arabic-Indic digits to ASCII standard digits."""
    return "".join(URDU_DIGITS_MAP.get(char, char) for char in text)


def normalize_tokens(text: str) -> list[str]:
    """Tokenizes and cleans text for number parsing."""
    text = convert_urdu_digits(text)
    # Remove currency words and punctuations
    clean = re.sub(r"[,\.!\?]", " ", text)
    return [t.lower().strip() for t in clean.split() if t.strip()]


def parse_numeric_literal(text: str) -> Optional[int]:
    """Finds pure integer digits in text (e.g. '400 rupay' -> 400, '۴۰۰' -> 400)."""
    text_with_ascii = convert_urdu_digits(text)
    # Search for explicit digits
    matches = re.findall(r"\b\d+\b", text_with_ascii)
    if matches:
        # If multiple numbers exist, usually the amount is the largest or the one closest to 'rupay'
        # Check if one is directly attached to currency
        curr_match = re.search(r"(\d+)\s*(?:rupay|rupees|rs|روپے|کا|کی)", text_with_ascii, re.IGNORECASE)
        if curr_match:
            return int(curr_match.group(1))
        # Otherwise return the last digit group or primary amount
        return int(matches[-1])
    return None


def parse_word_number(text: str) -> Optional[int]:
    """Parses Roman-Urdu or Urdu script number phrases into an integer."""
    text_lower = convert_urdu_digits(text.lower().strip())

    # Check for direct special combinations first
    for phrase, val in SPECIAL_COMBINATIONS.items():
        if phrase in text_lower:
            return val

    tokens = normalize_tokens(text_lower)
    if not tokens:
        return None

    # Try matching sequences of number tokens
    # e.g., ["char", "sau"], ["paanch", "sau", "pachaas"], ["do", "hazaar", "panch", "sau"]
    current_val = 0
    total = 0
    found_any = False

    i = 0
    while i < len(tokens):
        token = tokens[i]

        # Check two-word special combination
        if i + 1 < len(tokens):
            two_word = f"{token} {tokens[i+1]}"
            if two_word in SPECIAL_COMBINATIONS:
                val = SPECIAL_COMBINATIONS[two_word]
                total += val
                found_any = True
                i += 2
                continue

        # Check if token is a direct base number
        if token in BASE_NUMBERS:
            current_val = BASE_NUMBERS[token]
            found_any = True
            # Look ahead to see if next token is a multiplier
            if i + 1 < len(tokens) and tokens[i + 1] in MULTIPLIERS:
                multiplier = MULTIPLIERS[tokens[i + 1]]
                total += current_val * multiplier
                current_val = 0
                i += 2
                continue
            else:
                total += current_val
                current_val = 0
                i += 1
                continue

        # Check if token is a standalone multiplier (e.g. "sau" = 100, "hazaar" = 1000)
        elif token in MULTIPLIERS:
            multiplier = MULTIPLIERS[token]
            if current_val == 0:
                current_val = 1
            total += current_val * multiplier
            current_val = 0
            found_any = True
            i += 1
            continue

        # Check if token itself is numeric
        elif token.isdigit():
            val = int(token)
            found_any = True
            if i + 1 < len(tokens) and tokens[i + 1] in MULTIPLIERS:
                multiplier = MULTIPLIERS[tokens[i + 1]]
                total += val * multiplier
                i += 2
                continue
            else:
                total += val
                i += 1
                continue

        i += 1

    if found_any and total > 0:
        return total
    return None


def extract_amount(text: str) -> Optional[int]:
    """Combines digit parsing and word-based parsing to extract the transaction amount."""
    # First priority: check for explicit digits (e.g. 400, 360, 1500)
    digit_val = parse_numeric_literal(text)
    if digit_val is not None and digit_val > 0:
        return digit_val

    # Second priority: word numbers (e.g. "char sau", "paanch sau", "dedh sau", "دو سو")
    word_val = parse_word_number(text)
    if word_val is not None and word_val > 0:
        return word_val

    return None
