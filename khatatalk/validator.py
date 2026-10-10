"""Validation rules for KhataTalk ledger transactions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from khatatalk.config import MAX_TRANSACTION_AMOUNT


@dataclass
class ValidationResult:
    is_valid: bool
    error: Optional[str] = None
    warning: Optional[str] = None
    needs_override: bool = False


def validate_transaction(
    customer_name: Optional[str],
    tx_type: str,
    amount: int,
    current_balance: int = 0,
    max_amount: int = MAX_TRANSACTION_AMOUNT,
) -> ValidationResult:
    """Validates transaction data before presenting for user confirmation.

    Rejects:
    - Missing customer name
    - Invalid transaction type
    - Non-positive amount (amount <= 0)
    - Absurd amount (> max_amount)

    Warns:
    - Payment exceeding current outstanding balance
    """
    # 1. Missing customer name
    if not customer_name or not str(customer_name).strip():
        return ValidationResult(
            is_valid=False,
            error="Customer name is required.",
        )

    # 2. Transaction type
    if tx_type not in ("credit", "payment"):
        return ValidationResult(
            is_valid=False,
            error=f"Invalid transaction type '{tx_type}'. Must be 'credit' or 'payment'.",
        )

    # 3. Non-positive amount
    if amount is None or amount <= 0:
        return ValidationResult(
            is_valid=False,
            error=f"Transaction amount must be greater than 0 (got {amount}).",
        )

    # 4. Absurdly large amount
    if amount > max_amount:
        return ValidationResult(
            is_valid=False,
            error=(
                f"Amount of Rs {amount:,} exceeds the maximum safety limit "
                f"of Rs {max_amount:,}."
            ),
        )

    # 5. Payment greater than current balance (soft warning, can override)
    if tx_type == "payment" and current_balance >= 0 and amount > current_balance:
        warning_msg = (
            f"Payment of Rs {amount} exceeds current balance of Rs {current_balance} "
            f"(advance of Rs {amount - current_balance})."
        )
        return ValidationResult(
            is_valid=True,
            warning=warning_msg,
            needs_override=True,
        )

    return ValidationResult(is_valid=True)
