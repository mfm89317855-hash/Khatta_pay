"""Intent classification router for shopkeeper utterances."""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from khatatalk.llm import OllamaClientError, query_json
from khatatalk.prompts import ROUTER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

ALLOWED_INTENTS = {
    "add_credit",
    "add_payment",
    "ask_balance",
    "daily_summary",
    "top_debtors",
    "draft_reminder",
    "unknown",
}


def rule_based_classify(text: str) -> str:
    """Fast, deterministic keyword/regex heuristic for fallback or validation."""
    t = text.lower().strip()

    # Reminder
    if any(k in t for k in ["reminder", "taqaza", "message banao", "sms", "پیغام", "یاد دہانی"]):
        return "draft_reminder"

    # Top debtors
    if any(k in t for k in ["top debtor", "sab se zyada", "sabse zyada", "سب سے زیادہ", "highest udhaar", "kis ka zyada"]):
        return "top_debtors"

    # Daily summary
    if any(k in t for k in ["aaj ka hisaab", "daily summary", "aaj ka total", "aaj ka khata", "آج کا حساب", "today summary"]):
        return "daily_summary"

    # Balance inquiry
    if any(k in t for k in ["kitna baqaya", "kitna udhaar", "kitna dena", "hisaab kitna", "balance", "کتنا باقی", "کتنا ادھار", "کا حساب"]):
        return "ask_balance"

    # Credit given (udhaar / khata)
    if any(k in t for k in ["udhaar", "udhar", "khata", "ادھار", "کھاتہ"]) and not any(k in t for k in ["wapas", "ada", "wasool", "utara"]):
        return "add_credit"

    # Payment received
    if any(k in t for k in ["wapas", "jama", "wasool", "ada", "دیئے", "واپس", "جمع"]):
        return "add_payment"

    # Credit given fallback
    if any(k in t for k in ["udhaar", "udhar", "khata", "ادھار", "کھاتہ"]):
        return "add_credit"

    return "unknown"


def classify_intent(text: str, llm_client: Optional[Any] = None) -> str:
    """Classifies spoken utterance into one of the allowed ledger intents.

    Uses LLM with few-shot JSON format, falling back gracefully to heuristic matching.
    """
    if not text or not text.strip():
        return "unknown"

    # Try LLM classification first
    try:
        data = query_json(
            prompt=f"Utterance: {text.strip()}",
            system=ROUTER_SYSTEM_PROMPT,
            client=llm_client,
        )
        intent = data.get("intent", "").strip().lower()
        if intent in ALLOWED_INTENTS:
            return intent
        logger.warning("LLM returned non-standard intent: %s", intent)
    except (OllamaClientError, Exception) as err:
        logger.info("LLM intent classification unavailable or failed (%s). Falling back to heuristic.", err)

    # Heuristic fallback
    return rule_based_classify(text)
