"""Tests for customer name resolver with honorific stripping and fuzzy matching."""

import os
import tempfile
import pytest

from khatatalk.db import init_db, add_customer
from khatatalk.resolver import clean_customer_name, resolve_customer


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


def test_clean_customer_name_honorifics():
    assert clean_customer_name("Ahmed bhai") == "Ahmed"
    assert clean_customer_name("Tariq sahab") == "Tariq"
    assert clean_customer_name("Fatima baji") == "Fatima"
    assert clean_customer_name("Imran uncle") == "Imran"
    assert clean_customer_name("Ahmad bhai ko") == "Ahmad"
    assert clean_customer_name("Bilal ne") == "Bilal"
    assert clean_customer_name("احمد بھائی") == "احمد"


def test_resolve_exact_match(test_db):
    add_customer("Ahmed Khan", db_path=test_db)
    add_customer("Bilal Siddiqui", db_path=test_db)

    # Exact match case-insensitive
    res = resolve_customer("ahmed khan", db_path=test_db)
    assert res.status == "matched"
    assert res.resolved_name == "Ahmed Khan"
    assert res.confidence == 100.0

    # Match with honorific stripped
    res2 = resolve_customer("Bilal Siddiqui bhai", db_path=test_db)
    assert res2.status == "matched"
    assert res2.resolved_name == "Bilal Siddiqui"


def test_resolve_fuzzy_match(test_db):
    add_customer("Kamran", db_path=test_db)

    # Typo: "Kamraan" or "Kamran sb"
    res = resolve_customer("Kamraan", db_path=test_db)
    assert res.status == "matched"
    assert res.resolved_name == "Kamran"
    assert res.confidence >= 80.0


def test_resolve_ambiguous_matches(test_db):
    add_customer("Tariq Mahmood", db_path=test_db)
    add_customer("Tariq Mehmood", db_path=test_db)

    res = resolve_customer("Tariq", db_path=test_db)
    assert res.status == "ambiguous"
    assert res.clarification_question is not None
    assert "Which customer did you mean?" in res.clarification_question


def test_resolve_new_customer(test_db):
    add_customer("Usman", db_path=test_db)

    # Completely different person
    res = resolve_customer("Rashid Minhas", db_path=test_db)
    assert res.status == "new_customer"
    assert res.resolved_name == "Rashid Minhas"
    assert "Add as new customer" in res.message
