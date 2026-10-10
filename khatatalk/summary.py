"""Query answering and reminder drafting using SQL results and polite phrasing."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from khatatalk.db import daily_summary as sql_daily_summary
from khatatalk.db import get_balance as sql_get_balance
from khatatalk.db import top_debtors as sql_top_debtors
from khatatalk.llm import OllamaClientError, query_text
from khatatalk.prompts import REMINDER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def answer_balance_query(
    customer_id: int,
    customer_name: str,
    db_path: Optional[Union[str, Path]] = None,
    llm_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Answers customer balance inquiry strictly using SQLite balance."""
    balance = sql_get_balance(customer_id, db_path=db_path)

    if balance > 0:
        base_message = f"{customer_name} ka kul baqaya Rs {balance:,} hai (udhaar)."
    elif balance == 0:
        base_message = f"{customer_name} ka hisaab barabar hai (Rs 0 baqaya)."
    else:
        base_message = f"{customer_name} ke Rs {abs(balance):,} dukan ke paas jama (advance) hain."

    # Optional polite Roman Urdu phrasing via LLM
    text_answer = base_message
    if llm_client is not None:
        try:
            prompt = (
                f"Customer: {customer_name}\n"
                f"Exact Balance: {balance} PKR\n"
                f"Phrase this balance statement clearly and politely in one short sentence in Roman Urdu. "
                f"Do not change or invent any numbers."
            )
            response = query_text(
                prompt=prompt,
                system="You are a shop ledger assistant. State the balance using only the numbers provided.",
                client=llm_client,
            )
            if response and str(balance) in response:
                text_answer = response
        except Exception:
            pass

    return {
        "customer_id": customer_id,
        "customer": customer_name,
        "balance": balance,
        "text_response": text_answer,
    }


def answer_daily_summary(
    date_str: Optional[str] = None,
    db_path: Optional[Union[str, Path]] = None,
    llm_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Summarises today's transactions from SQL."""
    data = sql_daily_summary(date_str=date_str, db_path=db_path)
    total_credit = data["total_credit"]
    total_payment = data["total_payment"]
    net = data["net_change"]
    count = data["transaction_count"]

    text_response = (
        f"📅 Aaj ka hisaab ({data['date']}):\n"
        f"• Kul Udhaar (Credit): Rs {total_credit:,}\n"
        f"• Kul Wasooli (Payment): Rs {total_payment:,}\n"
        f"• Net Tabdeeli: Rs {net:,}\n"
        f"• Kul Transactions: {count}"
    )

    return {
        **data,
        "text_response": text_response,
    }


def answer_top_debtors(
    limit: int = 5,
    db_path: Optional[Union[str, Path]] = None,
    llm_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Retrieves top debtors from SQL and formats list."""
    debtors = sql_top_debtors(limit=limit, db_path=db_path)

    if not debtors:
        text_response = "Sab accounts clear hain! Koi baqaya udhaar nahi hai."
    else:
        lines = [f"📊 Sab se zyada udhaar (Top {len(debtors)}):"]
        for idx, d in enumerate(debtors, start=1):
            lines.append(f"{idx}. {d['name']} — Rs {d['balance']:,}")
        text_response = "\n".join(lines)

    return {
        "debtors": debtors,
        "count": len(debtors),
        "text_response": text_response,
    }


def draft_reminder(
    customer_id: int,
    customer_name: str,
    db_path: Optional[Union[str, Path]] = None,
    llm_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Generates a polite reminder message using customer name and exact balance from SQLite."""
    balance = sql_get_balance(customer_id, db_path=db_path)

    if balance <= 0:
        return {
            "customer_id": customer_id,
            "customer": customer_name,
            "balance": balance,
            "message": f"{customer_name} ka koi udhaar baqaya nahi hai (Balance: Rs {balance}). Reminder bhejne ki zaroorat nahi.",
            "can_send": False,
        }

    default_reminder = (
        f"Assalam-o-Alaikum {customer_name} bhai, umeed hai aap theek honge. "
        f"Dukan ka pichla hisaab Rs {balance:,} baqaya hai. "
        f"Baraye meherbani jab asani ho ada farma dein. Shukriya!"
    )

    final_message = default_reminder
    if llm_client is not None:
        try:
            prompt = (
                f"Customer name: {customer_name}\n"
                f"Exact outstanding balance: {balance} PKR\n"
                f"Draft a polite 2-sentence WhatsApp reminder in Roman Urdu asking to clear this balance."
            )
            llm_draft = query_text(
                prompt=prompt,
                system=REMINDER_SYSTEM_PROMPT,
                client=llm_client,
            )
            # Verify the exact number wasn't mutated
            if llm_draft and str(balance) in llm_draft:
                final_message = llm_draft
        except Exception as e:
            logger.info("Using default reminder template (%s)", e)

    return {
        "customer_id": customer_id,
        "customer": customer_name,
        "balance": balance,
        "message": final_message,
        "can_send": True,
    }
