"""Tests for SQLite database operations and balance math."""

import os
import tempfile
import pytest

from khatatalk.db import (
    init_db,
    add_customer,
    get_customer_by_id,
    get_customer_by_name,
    add_transaction,
    get_balance,
    list_customers,
    find_customers_like,
    top_debtors,
    daily_summary,
)


@pytest.fixture
def test_db():
    """Creates a temporary database for test isolation."""
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


def test_init_and_add_customer(test_db):
    cid = add_customer("Ahmed", db_path=test_db)
    assert cid > 0

    # Case-insensitive duplicate returns existing ID
    cid2 = add_customer("ahmed", db_path=test_db)
    assert cid == cid2

    # Whitespace trimming
    cid3 = add_customer("  Ahmed  ", db_path=test_db)
    assert cid == cid3

    customer = get_customer_by_name("Ahmed", db_path=test_db)
    assert customer is not None
    assert customer["name"] == "Ahmed"

    # Empty name fails
    with pytest.raises(ValueError):
        add_customer("   ", db_path=test_db)


def test_balance_computation(test_db):
    """Verifies that balance = SUM(credit) - SUM(payment) strictly in SQL."""
    cid = add_customer("Bilal", db_path=test_db)

    # Initially zero balance
    assert get_balance(cid, db_path=test_db) == 0

    # Add credit of 500 PKR
    add_transaction(cid, type="credit", amount=500, item="sugar", quantity="2kg", db_path=test_db)
    assert get_balance(cid, db_path=test_db) == 500

    # Add another credit of 250 PKR
    add_transaction(cid, type="credit", amount=250, item="oil", db_path=test_db)
    assert get_balance(cid, db_path=test_db) == 750

    # Partial payment of 300 PKR
    add_transaction(cid, type="payment", amount=300, db_path=test_db)
    assert get_balance(cid, db_path=test_db) == 450

    # Full payment of remaining 450 PKR
    add_transaction(cid, type="payment", amount=450, db_path=test_db)
    assert get_balance(cid, db_path=test_db) == 0


def test_transaction_constraints(test_db):
    cid = add_customer("Tariq", db_path=test_db)

    # Amount <= 0 must fail
    with pytest.raises(ValueError):
        add_transaction(cid, type="credit", amount=0, db_path=test_db)

    with pytest.raises(ValueError):
        add_transaction(cid, type="credit", amount=-100, db_path=test_db)

    # Invalid transaction type
    with pytest.raises(ValueError):
        add_transaction(cid, type="refund", amount=100, db_path=test_db)

    # Non-existent customer
    with pytest.raises(ValueError):
        add_transaction(99999, type="credit", amount=100, db_path=test_db)


def test_top_debtors(test_db):
    c1 = add_customer("Zahid", db_path=test_db)
    c2 = add_customer("Hamza", db_path=test_db)
    c3 = add_customer("Usman", db_path=test_db)

    add_transaction(c1, "credit", 1200, db_path=test_db)
    add_transaction(c2, "credit", 5000, db_path=test_db)
    add_transaction(c3, "credit", 800, db_path=test_db)
    add_transaction(c3, "payment", 800, db_path=test_db)  # balance = 0

    debtors = top_debtors(limit=5, db_path=test_db)
    assert len(debtors) == 2  # c3 has 0 balance, so not a debtor
    assert debtors[0]["name"] == "Hamza"
    assert debtors[0]["balance"] == 5000
    assert debtors[1]["name"] == "Zahid"
    assert debtors[1]["balance"] == 1200


def test_daily_summary_and_search(test_db):
    c1 = add_customer("Kamran Khan", db_path=test_db)
    c2 = add_customer("Imran Ali", db_path=test_db)

    add_transaction(c1, "credit", 1000, item="atta", db_path=test_db)
    add_transaction(c1, "payment", 400, db_path=test_db)
    add_transaction(c2, "credit", 600, item="chai", db_path=test_db)

    summary = daily_summary(db_path=test_db)
    assert summary["total_credit"] == 1600
    assert summary["total_payment"] == 400
    assert summary["net_change"] == 1200
    assert summary["transaction_count"] == 3
    assert len(summary["transactions"]) == 3

    # Search like
    matches = find_customers_like("kamran", db_path=test_db)
    assert len(matches) == 1
    assert matches[0]["name"] == "Kamran Khan"
    assert matches[0]["balance"] == 600
