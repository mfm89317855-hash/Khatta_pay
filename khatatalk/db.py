"""SQLite database schema and query functions for KhataTalk."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from khatatalk.config import DEFAULT_DB_PATH


def get_connection(db_path: Optional[Union[str, Path]] = None) -> sqlite3.Connection:
    """Returns a SQLite connection with foreign keys enabled and row factory set to sqlite3.Row."""
    target_path = str(db_path or DEFAULT_DB_PATH)
    conn = sqlite3.connect(target_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[Union[str, Path]] = None) -> None:
    """Initialises the database tables and indexes if they do not exist."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL COLLATE NOCASE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
                type TEXT NOT NULL CHECK(type IN ('credit', 'payment')),
                item TEXT,
                quantity TEXT,
                amount INTEGER NOT NULL CHECK(amount > 0),
                note TEXT,
                raw_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_tx_customer ON transactions(customer_id);"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_tx_created_at ON transactions(created_at);"
        )
        conn.commit()


def add_customer(name: str, db_path: Optional[Union[str, Path]] = None) -> int:
    """Adds a new customer or returns the ID of an existing customer with the same name."""
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Customer name cannot be empty.")

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM customers WHERE name = ? COLLATE NOCASE;",
            (clean_name,),
        )
        row = cursor.fetchone()
        if row:
            return int(row["id"])

        cursor.execute(
            "INSERT INTO customers (name) VALUES (?);",
            (clean_name,),
        )
        conn.commit()
        return int(cursor.lastrowid)


def get_customer_by_id(customer_id: int, db_path: Optional[Union[str, Path]] = None) -> Optional[Dict[str, Any]]:
    """Returns a customer dict by ID or None."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, created_at FROM customers WHERE id = ?;",
            (customer_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return dict(row)


def get_customer_by_name(name: str, db_path: Optional[Union[str, Path]] = None) -> Optional[Dict[str, Any]]:
    """Returns a customer dict by exact (case-insensitive) name or None."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, created_at FROM customers WHERE name = ? COLLATE NOCASE;",
            (name.strip(),),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return dict(row)


def add_transaction(
    customer_id: int,
    type: str,
    amount: int,
    item: Optional[str] = None,
    quantity: Optional[str] = None,
    note: Optional[str] = None,
    raw_text: Optional[str] = None,
    db_path: Optional[Union[str, Path]] = None,
) -> int:
    """Inserts a credit or payment transaction for a customer."""
    if type not in ("credit", "payment"):
        raise ValueError("Transaction type must be 'credit' or 'payment'.")
    if amount <= 0:
        raise ValueError("Transaction amount must be strictly greater than 0.")

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        # Verify customer exists
        cursor.execute("SELECT id FROM customers WHERE id = ?;", (customer_id,))
        if not cursor.fetchone():
            raise ValueError(f"Customer ID {customer_id} not found.")

        cursor.execute(
            """
            INSERT INTO transactions (customer_id, type, amount, item, quantity, note, raw_text)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                customer_id,
                type,
                int(amount),
                item.strip() if item else None,
                quantity.strip() if quantity else None,
                note.strip() if note else None,
                raw_text.strip() if raw_text else None,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def get_balance(customer_id: int, db_path: Optional[Union[str, Path]] = None) -> int:
    """Computes and returns the customer's balance in SQL: SUM(credit) - SUM(payment).

    A positive balance means the customer owes money (udhaar / debt).
    A zero or negative balance means paid up or credit advance.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COALESCE(
                SUM(CASE WHEN type = 'credit' THEN amount ELSE -amount END),
                0
            ) AS balance
            FROM transactions
            WHERE customer_id = ?;
            """,
            (customer_id,),
        )
        row = cursor.fetchone()
        return int(row["balance"]) if row else 0


def list_customers(db_path: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
    """Returns all customers with their computed current balance and last transaction timestamp."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                c.id, 
                c.name, 
                c.created_at,
                COALESCE(SUM(CASE WHEN t.type = 'credit' THEN t.amount ELSE -t.amount END), 0) AS balance,
                COUNT(t.id) as transaction_count,
                MAX(t.created_at) as last_transaction_at
            FROM customers c
            LEFT JOIN transactions t ON c.id = t.customer_id
            GROUP BY c.id, c.name, c.created_at
            ORDER BY c.name COLLATE NOCASE ASC;
            """
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def find_customers_like(name: str, db_path: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
    """Finds customers with substring match in their name, returning them with balance."""
    clean_name = name.strip()
    if not clean_name:
        return []

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                c.id, 
                c.name, 
                c.created_at,
                COALESCE(SUM(CASE WHEN t.type = 'credit' THEN t.amount ELSE -t.amount END), 0) AS balance
            FROM customers c
            LEFT JOIN transactions t ON c.id = t.customer_id
            WHERE c.name LIKE ? ESCAPE '\\'
            GROUP BY c.id, c.name, c.created_at
            ORDER BY c.name COLLATE NOCASE ASC;
            """,
            (f"%{clean_name}%",),
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def top_debtors(limit: int = 5, db_path: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
    """Returns top customers with positive balance (money owed), ordered highest first."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                c.id, 
                c.name, 
                c.created_at,
                COALESCE(SUM(CASE WHEN t.type = 'credit' THEN t.amount ELSE -t.amount END), 0) AS balance
            FROM customers c
            JOIN transactions t ON c.id = t.customer_id
            GROUP BY c.id, c.name, c.created_at
            HAVING balance > 0
            ORDER BY balance DESC
            LIMIT ?;
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def daily_summary(
    date_str: Optional[str] = None,
    db_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Returns summary of transactions for a specific date (YYYY-MM-DD), default today."""
    target_date = date_str or datetime.now().strftime("%Y-%m-%d")

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                COALESCE(SUM(CASE WHEN type = 'credit' THEN amount ELSE 0 END), 0) AS total_credit,
                COALESCE(SUM(CASE WHEN type = 'payment' THEN amount ELSE 0 END), 0) AS total_payment,
                COUNT(id) AS transaction_count
            FROM transactions
            WHERE date(created_at) = date(?);
            """,
            (target_date,),
        )
        stat = dict(cursor.fetchone() or {"total_credit": 0, "total_payment": 0, "transaction_count": 0})

        # Fetch individual transactions for today
        cursor.execute(
            """
            SELECT 
                t.id,
                c.name AS customer_name,
                t.type,
                t.amount,
                t.item,
                t.quantity,
                t.note,
                t.raw_text,
                t.created_at
            FROM transactions t
            JOIN customers c ON t.customer_id = c.id
            WHERE date(t.created_at) = date(?)
            ORDER BY t.created_at DESC;
            """,
            (target_date,),
        )
        tx_rows = [dict(r) for r in cursor.fetchall()]

    return {
        "date": target_date,
        "total_credit": int(stat["total_credit"]),
        "total_payment": int(stat["total_payment"]),
        "net_change": int(stat["total_credit"] - stat["total_payment"]),
        "transaction_count": int(stat["transaction_count"]),
        "transactions": tx_rows,
    }


def get_customer_statement(
    customer_id: int,
    limit: int = 50,
    db_path: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """Returns the transaction history statement for a customer."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, type, amount, item, quantity, note, raw_text, created_at
            FROM transactions
            WHERE customer_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?;
            """,
            (customer_id, limit),
        )
        return [dict(r) for r in cursor.fetchall()]
