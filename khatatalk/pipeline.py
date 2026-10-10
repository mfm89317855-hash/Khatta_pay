"""End-to-end pipeline orchestrating STT, routing, parsing, resolution, validation, and confirmation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Union

from khatatalk.db import add_customer, add_transaction, get_balance, get_customer_by_id
from khatatalk.parser import parse_target_customer, parse_transaction
from khatatalk.resolver import ResolutionResult, resolve_customer
from khatatalk.router import classify_intent
from khatatalk.summary import (
    answer_balance_query,
    answer_daily_summary,
    answer_top_debtors,
    draft_reminder,
)
from khatatalk.validator import ValidationResult, validate_transaction

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    input_text: str
    intent: str
    status: str  # "needs_confirmation", "completed", "clarification_needed", "error"
    requires_confirmation: bool = False
    confirmation_prompt: Optional[str] = None
    pending_transaction: Optional[Dict[str, Any]] = None
    resolution: Optional[ResolutionResult] = None
    validation: Optional[ValidationResult] = None
    query_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    warning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_text": self.input_text,
            "intent": self.intent,
            "status": self.status,
            "requires_confirmation": self.requires_confirmation,
            "confirmation_prompt": self.confirmation_prompt,
            "pending_transaction": self.pending_transaction,
            "query_result": self.query_result,
            "error": self.error,
            "warning": self.warning,
        }


def process_utterance(
    text: str,
    db_path: Optional[Union[str, Path]] = None,
    llm_client: Optional[Any] = None,
) -> PipelineResult:
    """Processes an utterance through router, parser, resolver, and validator.

    IMPORTANT: This function NEVER writes to the database for transactions.
    It returns a pending entry with `requires_confirmation = True`.
    """
    clean_text = text.strip()
    if not clean_text:
        return PipelineResult(
            input_text="",
            intent="unknown",
            status="error",
            error="Baraye meherbani aawaz ya text darj karein (Please provide audio or text).",
        )

    # 1. Route Intent
    intent = classify_intent(clean_text, llm_client=llm_client)

    # 2. Handle non-transaction queries
    if intent == "daily_summary":
        summary_res = answer_daily_summary(db_path=db_path, llm_client=llm_client)
        return PipelineResult(
            input_text=clean_text,
            intent=intent,
            status="completed",
            query_result=summary_res,
        )

    if intent == "top_debtors":
        debtors_res = answer_top_debtors(db_path=db_path, llm_client=llm_client)
        return PipelineResult(
            input_text=clean_text,
            intent=intent,
            status="completed",
            query_result=debtors_res,
        )

    if intent == "ask_balance":
        target_name = parse_target_customer(clean_text, llm_client=llm_client)
        resolution = resolve_customer(target_name, db_path=db_path)

        if resolution.status == "matched" and resolution.customer_id is not None:
            ans = answer_balance_query(
                customer_id=resolution.customer_id,
                customer_name=resolution.resolved_name,
                db_path=db_path,
                llm_client=llm_client,
            )
            return PipelineResult(
                input_text=clean_text,
                intent=intent,
                status="completed",
                resolution=resolution,
                query_result=ans,
            )
        elif resolution.status == "ambiguous":
            return PipelineResult(
                input_text=clean_text,
                intent=intent,
                status="clarification_needed",
                resolution=resolution,
                error=resolution.clarification_question,
            )
        else:
            return PipelineResult(
                input_text=clean_text,
                intent=intent,
                status="error",
                resolution=resolution,
                error=f"Customer '{target_name}' ledger mein mojood nahi hai (Customer not found).",
            )

    if intent == "draft_reminder":
        target_name = parse_target_customer(clean_text, llm_client=llm_client)
        resolution = resolve_customer(target_name, db_path=db_path)

        if resolution.status == "matched" and resolution.customer_id is not None:
            reminder_res = draft_reminder(
                customer_id=resolution.customer_id,
                customer_name=resolution.resolved_name,
                db_path=db_path,
                llm_client=llm_client,
            )
            return PipelineResult(
                input_text=clean_text,
                intent=intent,
                status="completed",
                resolution=resolution,
                query_result=reminder_res,
            )
        elif resolution.status == "ambiguous":
            return PipelineResult(
                input_text=clean_text,
                intent=intent,
                status="clarification_needed",
                resolution=resolution,
                error=resolution.clarification_question,
            )
        else:
            return PipelineResult(
                input_text=clean_text,
                intent=intent,
                status="error",
                resolution=resolution,
                error=f"Customer '{target_name}' ledger mein nahi hai.",
            )

    if intent not in ("add_credit", "add_payment"):
        return PipelineResult(
            input_text=clean_text,
            intent="unknown",
            status="error",
            error="Baat samajh nahi aayi. Baraye meherbani wazeh bolain (Unrecognized intent).",
        )

    # 3. For add_credit / add_payment: Parse Transaction
    parsed = parse_transaction(
        text=clean_text,
        default_type="credit" if intent == "add_credit" else "payment",
        llm_client=llm_client,
    )

    # 4. Resolve Customer Name
    resolution = resolve_customer(parsed.customer, db_path=db_path)

    if resolution.status == "ambiguous":
        return PipelineResult(
            input_text=clean_text,
            intent=intent,
            status="clarification_needed",
            resolution=resolution,
            error=resolution.clarification_question,
        )

    # Current balance if existing customer
    current_bal = 0
    if resolution.status == "matched" and resolution.customer_id is not None:
        current_bal = get_balance(resolution.customer_id, db_path=db_path)

    # 5. Validate Transaction Rules
    val = validate_transaction(
        customer_name=resolution.resolved_name,
        tx_type=parsed.type,
        amount=parsed.amount,
        current_balance=current_bal,
    )

    if not val.is_valid:
        return PipelineResult(
            input_text=clean_text,
            intent=intent,
            status="error",
            resolution=resolution,
            validation=val,
            error=val.error,
        )

    # Build readable confirmation text
    type_urdu = "udhaar" if parsed.type == "credit" else "wasooli / payment"
    item_details = ""
    if parsed.item:
        qty_str = f" ({parsed.quantity})" if parsed.quantity else ""
        item_details = f" [{parsed.item}{qty_str}]"

    new_cust_note = " (New Customer)" if resolution.status == "new_customer" else ""
    prompt_text = f"{resolution.resolved_name}{new_cust_note} — {parsed.amount:,} rupay {type_urdu}{item_details}. Save entry?"

    if parsed.amount_discrepancy:
        prompt_text += f"\n⚠️ Note: Extracted amount Rs {parsed.amount} differs from detected word count Rs {parsed.cross_check_amount}. Please verify."

    if val.warning:
        prompt_text += f"\n⚠️ Warning: {val.warning}"

    pending_tx = {
        "customer_id": resolution.customer_id,
        "customer_name": resolution.resolved_name,
        "is_new_customer": resolution.status == "new_customer",
        "type": parsed.type,
        "amount": parsed.amount,
        "item": parsed.item,
        "quantity": parsed.quantity,
        "raw_text": clean_text,
        "current_balance": current_bal,
    }

    # CONFIRM-BEFORE-SAVE GUARANTEE: Never written to DB here!
    return PipelineResult(
        input_text=clean_text,
        intent=intent,
        status="needs_confirmation",
        requires_confirmation=True,
        confirmation_prompt=prompt_text,
        pending_transaction=pending_tx,
        resolution=resolution,
        validation=val,
        warning=val.warning,
    )


def commit_transaction(
    pending_tx: Dict[str, Any],
    db_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Saves a confirmed pending transaction to SQLite.

    Returns the updated customer balance and transaction ID.
    """
    cust_id = pending_tx.get("customer_id")
    cust_name = pending_tx.get("customer_name", "").strip()

    if not cust_name:
        raise ValueError("Cannot commit transaction without customer name.")

    # Create new customer if needed
    if cust_id is None or pending_tx.get("is_new_customer"):
        cust_id = add_customer(cust_name, db_path=db_path)

    tx_id = add_transaction(
        customer_id=cust_id,
        type=pending_tx["type"],
        amount=pending_tx["amount"],
        item=pending_tx.get("item"),
        quantity=pending_tx.get("quantity"),
        raw_text=pending_tx.get("raw_text"),
        db_path=db_path,
    )

    new_balance = get_balance(cust_id, db_path=db_path)

    return {
        "transaction_id": tx_id,
        "customer_id": cust_id,
        "customer_name": cust_name,
        "amount": pending_tx["amount"],
        "type": pending_tx["type"],
        "new_balance": new_balance,
        "message": f"Kamyabi se save ho gaya! {cust_name} ka naya balance: Rs {new_balance:,}.",
    }
