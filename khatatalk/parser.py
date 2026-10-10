"""Transaction extraction and entity parsing from natural language utterances."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from khatatalk.llm import OllamaClientError, query_json
from khatatalk.numbers import extract_amount
from khatatalk.prompts import CUSTOMER_QUERY_PROMPT, PARSER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


@dataclass
class ParsedTransaction:
    customer: str
    item: Optional[str]
    quantity: Optional[str]
    amount: int
    type: str  # "credit" or "payment"
    raw_text: str
    cross_check_amount: Optional[int] = None
    amount_discrepancy: bool = False
    needs_amount_confirmation: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "customer": self.customer,
            "item": self.item,
            "quantity": self.quantity,
            "amount": self.amount,
            "type": self.type,
            "raw_text": self.raw_text,
            "cross_check_amount": self.cross_check_amount,
            "amount_discrepancy": self.amount_discrepancy,
            "needs_amount_confirmation": self.needs_amount_confirmation,
        }


def rule_based_extract(text: str, default_type: str = "credit") -> Dict[str, Any]:
    """Heuristic extraction fallback when LLM is unavailable."""
    raw = text.strip()
    # Determine type
    tx_type = default_type
    lower_text = raw.lower()
    if any(k in lower_text for k in ["udhaar", "udhar", "khata", "ادھار"]) and not any(k in lower_text for k in ["wapas", "wasool", "ada", "utara"]):
        tx_type = "credit"
    elif any(k in lower_text for k in ["wapas", "jama", "wasool", "ada", "واپس", "جمع"]):
        tx_type = "payment"
    elif any(k in lower_text for k in ["udhaar", "udhar", "khata", "ادھار"]):
        tx_type = "credit"

    # Extract amount using our number helper
    amount = extract_amount(raw) or 0

    # Extract customer name (usually the first word(s) before 'ko', 'ne', 'ka', or 'se')
    cust_match = re.search(r"^(.*?)(?:\s+(?:ko|ne|ka|se|say|کو|نے|کا|سے)\b)", raw, re.IGNORECASE)
    if cust_match:
        customer = cust_match.group(1).strip()
    else:
        # Take the first token
        words = raw.split()
        customer = words[0] if words else "Unknown"

    # Extract item and quantity if present
    item = None
    quantity = None
    qty_match = re.search(r"(\d+(?:\.\d+)?|\b(?:do|teen|char|paanch|ek|aik)\b)\s*(?:kilo|kg|dozen|darjan|paao|adad|لیٹر|کلو|درجن)\b", raw, re.IGNORECASE)
    if qty_match:
        quantity = qty_match.group(0).strip()

    for common_item in ["cheeni", "atta", "oil", "ghee", "anday", "chaawal", "chawal", "doodh", "chaye", "chai", "چینی", "آٹا", "تیل", "انڈے"]:
        if common_item in lower_text:
            item = common_item
            break

    return {
        "customer": customer,
        "item": item,
        "quantity": quantity,
        "amount": amount,
        "type": tx_type,
    }


def parse_transaction(
    text: str,
    default_type: str = "credit",
    llm_client: Optional[Any] = None,
) -> ParsedTransaction:
    """Parses a credit or payment transaction from shopkeeper utterance.

    Calls LLM for structured JSON extraction and CROSS-CHECKS the extracted amount
    with deterministic Urdu/Roman-Urdu number normaliser.
    If they disagree, flags `amount_discrepancy = True` and requests user confirmation.
    """
    raw_text = text.strip()
    data: Dict[str, Any] = {}

    # Try LLM first
    try:
        data = query_json(
            prompt=f"Utterance: {raw_text}",
            system=PARSER_SYSTEM_PROMPT,
            client=llm_client,
        )
    except (OllamaClientError, Exception) as err:
        logger.info("LLM parser unavailable (%s). Falling back to rule-based parser.", err)
        data = rule_based_extract(raw_text, default_type=default_type)

    customer = str(data.get("customer", "")).strip()
    item = data.get("item")
    if item is not None:
        item = str(item).strip() if str(item).strip().lower() != "null" else None

    quantity = data.get("quantity")
    if quantity is not None:
        quantity = str(quantity).strip() if str(quantity).strip().lower() != "null" else None

    # Handle amount from LLM
    try:
        llm_amount = int(data.get("amount", 0))
    except (ValueError, TypeError):
        llm_amount = 0

    tx_type = str(data.get("type", default_type)).strip().lower()
    if tx_type not in ("credit", "payment"):
        tx_type = default_type

    # CROSS-CHECK with Python number normalizer
    rule_amount = extract_amount(raw_text)

    final_amount = llm_amount
    discrepancy = False
    needs_confirm = False

    if rule_amount is not None and rule_amount > 0:
        if llm_amount == 0:
            final_amount = rule_amount
        elif llm_amount != rule_amount:
            # Conflict between LLM output and rule extractor!
            discrepancy = True
            needs_confirm = True
            # Prefer rule_amount if LLM gave 0 or obviously drifted
            logger.warning(
                "Amount discrepancy detected! LLM=%d vs RuleHelper=%d for text: '%s'",
                llm_amount,
                rule_amount,
                raw_text,
            )

    return ParsedTransaction(
        customer=customer,
        item=item,
        quantity=quantity,
        amount=final_amount,
        type=tx_type,
        raw_text=raw_text,
        cross_check_amount=rule_amount,
        amount_discrepancy=discrepancy,
        needs_amount_confirmation=needs_confirm,
    )


def parse_target_customer(text: str, llm_client: Optional[Any] = None) -> str:
    """Extracts customer name from balance inquiry or reminder request."""
    raw = text.strip()
    try:
        data = query_json(
            prompt=f"Utterance: {raw}",
            system=CUSTOMER_QUERY_PROMPT,
            client=llm_client,
        )
        cust = data.get("customer", "")
        if cust and str(cust).strip():
            return str(cust).strip()
    except Exception:
        pass

    # Heuristic fallback
    m = re.search(r"^(.*?)(?:\s+(?:ka|ki|ko|ke|se|say|کا|کی|کو|سے)\b)", raw, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    words = raw.split()
    return words[0] if words else raw
