"""Tests for end-to-end pipeline and confirm-before-save guarantee."""

import os
import tempfile
import pytest

from khatatalk.db import get_balance, init_db, list_customers
from khatatalk.pipeline import commit_transaction, process_utterance


@pytest.fixture
def test_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    import gc
    gc.collect()
    try:
        if os.path.exists(path):
            os.remove(path)
    except PermissionError:
        pass


def test_confirm_before_save_guarantee(test_db):
    """CRITICAL TEST: Verifies that processing an utterance NEVER writes to SQLite until commit."""
    utterance = "Ahmed ko do kilo cheeni udhaar di, 400 rupay"

    # 1. Initially database has zero customers
    assert len(list_customers(db_path=test_db)) == 0

    # 2. Process utterance through pipeline
    result = process_utterance(utterance, db_path=test_db)

    # 3. Verify it flagged for confirmation
    assert result.status == "needs_confirmation"
    assert result.requires_confirmation is True
    assert result.pending_transaction is not None
    assert "Ahmed" in result.confirmation_prompt
    assert "400" in result.confirmation_prompt

    # 4. GUARANTEE CHECK: Database must STILL have ZERO customers and zero transactions!
    assert len(list_customers(db_path=test_db)) == 0

    # 5. User cancels -> nothing is ever saved
    # (Simulated by simply discarding result.pending_transaction)
    assert len(list_customers(db_path=test_db)) == 0

    # 6. User clicks Confirm -> only now it writes to DB
    commit_res = commit_transaction(result.pending_transaction, db_path=test_db)
    assert commit_res["new_balance"] == 400
    assert commit_res["transaction_id"] > 0

    # 7. Database now has 1 customer with balance 400
    customers = list_customers(db_path=test_db)
    assert len(customers) == 1
    assert customers[0]["name"] == "Ahmed"
    assert customers[0]["balance"] == 400


def test_pipeline_queries_without_transactions(test_db):
    # Setup initial customer and transaction
    r1 = process_utterance("Ahmed ko 500 rupay udhaar diye", db_path=test_db)
    commit_transaction(r1.pending_transaction, db_path=test_db)

    # 1. Ask balance
    res_bal = process_utterance("Ahmed ka kitna baqaya hai?", db_path=test_db)
    assert res_bal.status == "completed"
    assert res_bal.intent == "ask_balance"
    assert res_bal.query_result["balance"] == 500
    assert "Rs 500" in res_bal.query_result["text_response"]

    # 2. Daily summary
    res_summary = process_utterance("Aaj ka hisaab dikhao", db_path=test_db)
    assert res_summary.status == "completed"
    assert res_summary.intent == "daily_summary"
    assert res_summary.query_result["total_credit"] == 500

    # 3. Top debtors
    res_debtors = process_utterance("Sab se zyada udhaar kiska hai?", db_path=test_db)
    assert res_debtors.status == "completed"
    assert res_debtors.intent == "top_debtors"
    assert len(res_debtors.query_result["debtors"]) == 1

    # 4. Draft reminder
    res_reminder = process_utterance("Ahmed ko payment reminder bhejo", db_path=test_db)
    assert res_reminder.status == "completed"
    assert res_reminder.intent == "draft_reminder"
    assert res_reminder.query_result["balance"] == 500
    assert "Rs 500" in res_reminder.query_result["message"]
