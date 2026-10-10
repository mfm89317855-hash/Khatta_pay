"""Tests for validator rules and Urdu / Roman-Urdu number normalisation."""

import pytest

from khatatalk.numbers import (
    convert_urdu_digits,
    extract_amount,
    parse_numeric_literal,
    parse_word_number,
)
from khatatalk.validator import validate_transaction


def test_urdu_number_words_normalisation():
    # Basic numbers
    assert parse_word_number("ek") == 1
    assert parse_word_number("do") == 2
    assert parse_word_number("char") == 4
    assert parse_word_number("paanch") == 5

    # Multiples of 100
    assert parse_word_number("char sau") == 400
    assert parse_word_number("paanch sau") == 500
    assert parse_word_number("teen sau") == 300
    assert parse_word_number("hazaar") == 1000
    assert parse_word_number("do hazaar") == 2000

    # Fractions / special combinations
    assert parse_word_number("dedh sau") == 150
    assert parse_word_number("dhai sau") == 250
    assert parse_word_number("dedh hazaar") == 1500

    # Urdu script
    assert parse_word_number("چار سو") == 400
    assert parse_word_number("ڈیڑھ سو") == 150
    assert parse_word_number("پانچ سو") == 500


def test_urdu_digit_characters():
    assert convert_urdu_digits("۴۰۰") == "400"
    assert convert_urdu_digits("۱۵۰") == "150"
    assert extract_amount("احمد کو ۴۰۰ روپے ادھار دیئے") == 400
    assert extract_amount("۳۶۰") == 360


def test_extract_amount_from_phrases():
    # Phrase with digits
    assert extract_amount("Ahmed ko do kilo cheeni udhaar di, 400 rupay") == 400
    assert extract_amount("Bilal ne 500 rupay wapas kiye") == 500
    assert extract_amount("ahmad bhai ko ek dozen anday udhaar, 360") == 360

    # Phrase with word numbers
    assert extract_amount("Ahmed ko char sau rupay udhaar di") == 400
    assert extract_amount("Usman ne paanch sau rupay ada kiye") == 500
    assert extract_amount("dedh sau rupay ka samaan") == 150


def test_validate_transaction_rules():
    # 1. Valid credit
    v = validate_transaction(customer_name="Ahmed", tx_type="credit", amount=400)
    assert v.is_valid is True
    assert v.error is None
    assert v.warning is None

    # 2. Missing customer name
    v_missing = validate_transaction(customer_name="", tx_type="credit", amount=400)
    assert v_missing.is_valid is False
    assert "Customer name is required" in v_missing.error

    # 3. Non-positive amount
    v_zero = validate_transaction(customer_name="Ahmed", tx_type="credit", amount=0)
    assert v_zero.is_valid is False
    assert "must be greater than 0" in v_zero.error

    v_neg = validate_transaction(customer_name="Ahmed", tx_type="credit", amount=-50)
    assert v_neg.is_valid is False
    assert "must be greater than 0" in v_neg.error

    # 4. Absurd amount
    v_absurd = validate_transaction(
        customer_name="Ahmed", tx_type="credit", amount=5_000_000, max_amount=1_000_000
    )
    assert v_absurd.is_valid is False
    assert "exceeds the maximum safety limit" in v_absurd.error

    # 5. Payment exceeding current balance (warning + override allowed)
    v_overpay = validate_transaction(
        customer_name="Bilal", tx_type="payment", amount=600, current_balance=200
    )
    assert v_overpay.is_valid is True  # Allowed with warning
    assert v_overpay.needs_override is True
    assert "exceeds current balance" in v_overpay.warning
