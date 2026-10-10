"""Tests for router, parser, and LLM JSON extraction with mocked LLM responses."""

import json
from unittest.mock import MagicMock
import pytest

from khatatalk.llm import InvalidJSONError, query_json
from khatatalk.parser import parse_target_customer, parse_transaction
from khatatalk.router import classify_intent


class MockOllamaClient:
    """Mock client returning predetermined responses."""

    def __init__(self, responses=None):
        self.responses = responses or []
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        if self.responses:
            resp = self.responses.pop(0)
            if isinstance(resp, Exception):
                raise resp
            return {"response": resp}
        return {"response": "{}"}


def test_router_classification_with_mock():
    mock_client = MockOllamaClient([
        json.dumps({"intent": "add_credit"}),
        json.dumps({"intent": "add_payment"}),
        json.dumps({"intent": "ask_balance"}),
    ])

    intent1 = classify_intent("Ahmed ko do kilo cheeni udhaar di, 400 rupay", llm_client=mock_client)
    assert intent1 == "add_credit"

    intent2 = classify_intent("Bilal ne 500 rupay wapas kiye", llm_client=mock_client)
    assert intent2 == "add_payment"

    intent3 = classify_intent("Ahmed ka kitna baqaya hai?", llm_client=mock_client)
    assert intent3 == "ask_balance"


def test_router_heuristic_fallback():
    # When LLM client is None or fails
    assert classify_intent("Ahmed ko do kilo cheeni udhaar di, 400 rupay") == "add_credit"
    assert classify_intent("Bilal ne 500 rupay wapas kiye") == "add_payment"
    assert classify_intent("Ahmed ka kitna baqaya hai?") == "ask_balance"
    assert classify_intent("Aaj ka hisaab dikhao") == "daily_summary"
    assert classify_intent("Sab se zyada udhaar kiska hai?") == "top_debtors"
    assert classify_intent("Tariq ko payment reminder bhejo") == "draft_reminder"


def test_parser_with_mock_llm():
    mock_client = MockOllamaClient([
        json.dumps({
            "customer": "Ahmed",
            "item": "cheeni",
            "quantity": "2 kilo",
            "amount": 400,
            "type": "credit"
        })
    ])

    tx = parse_transaction("Ahmed ko do kilo cheeni udhaar di, 400 rupay", llm_client=mock_client)
    assert tx.customer == "Ahmed"
    assert tx.item == "cheeni"
    assert tx.quantity == "2 kilo"
    assert tx.amount == 400
    assert tx.type == "credit"
    assert tx.amount_discrepancy is False


def test_parser_amount_cross_check_discrepancy():
    # LLM hallucinates 300, but spoken text explicitly has 400
    mock_client = MockOllamaClient([
        json.dumps({
            "customer": "Ahmed",
            "item": "cheeni",
            "quantity": "2 kilo",
            "amount": 300,  # Hallucinated
            "type": "credit"
        })
    ])

    tx = parse_transaction("Ahmed ko do kilo cheeni udhaar di, 400 rupay", llm_client=mock_client)
    assert tx.customer == "Ahmed"
    assert tx.amount_discrepancy is True
    assert tx.needs_amount_confirmation is True
    assert tx.cross_check_amount == 400


def test_parse_target_customer():
    mock_client = MockOllamaClient([
        json.dumps({"customer": "Kamran"})
    ])
    assert parse_target_customer("Kamran ka kitna baqaya hai?", llm_client=mock_client) == "Kamran"

    # Fallback without mock
    assert parse_target_customer("Bilal ka hisaab batao") == "Bilal"


def test_llm_json_retry_mechanism():
    # First response is malformed JSON, second response is valid JSON
    mock_client = MockOllamaClient([
        "Malformed string without JSON",
        json.dumps({"intent": "add_credit"}),
    ])

    result = query_json(prompt="test", system="test", client=mock_client, max_retries=2)
    assert result == {"intent": "add_credit"}
    assert len(mock_client.calls) == 2


def test_llm_json_retry_exhausted():
    # All retries fail
    mock_client = MockOllamaClient([
        "Invalid JSON 1",
        "Invalid JSON 2",
        "Invalid JSON 3",
    ])

    with pytest.raises(InvalidJSONError):
        query_json(prompt="test", system="test", client=mock_client, max_retries=2)
