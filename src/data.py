"""SQLite-backed customer database for the bank credit limit agent demo.

Persists customer accounts, balances, transactions, and credit limit changes
to /data/bank.db (or in-memory if the path isn't writable).
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from contextlib import contextmanager

DB_PATH = os.environ.get("BANK_DB_PATH", "/data/bank.db")

# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

def _get_db_path() -> str:
    """Return DB_PATH if writable directory exists, else use in-memory."""
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and os.path.isdir(db_dir):
        return DB_PATH
    # Fallback: try local directory
    local = os.path.join(os.path.dirname(__file__), "bank.db")
    return local


_DB = _get_db_path()


@contextmanager
def get_db():
    conn = sqlite3.connect(_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create tables and seed demo data if not already present."""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS customers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT,
                credit_score INTEGER,
                current_credit_limit REAL,
                account_age_months INTEGER,
                annual_income REAL,
                monthly_debt_payments REAL,
                utilization_rate REAL,
                recent_inquiries INTEGER,
                delinquencies_last_2y INTEGER
            );

            CREATE TABLE IF NOT EXISTS account_balances (
                customer_id TEXT PRIMARY KEY REFERENCES customers(id),
                checking_balance REAL DEFAULT 0,
                savings_balance REAL DEFAULT 0,
                credit_balance_owed REAL DEFAULT 0,
                last_updated TEXT
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT REFERENCES customers(id),
                timestamp TEXT NOT NULL,
                type TEXT NOT NULL,
                description TEXT,
                amount REAL NOT NULL,
                balance_after REAL
            );

            CREATE TABLE IF NOT EXISTS payment_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT REFERENCES customers(id),
                month TEXT NOT NULL,
                amount_due REAL,
                amount_paid REAL,
                on_time INTEGER
            );

            CREATE TABLE IF NOT EXISTS credit_limit_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT REFERENCES customers(id),
                timestamp TEXT NOT NULL,
                old_limit REAL,
                new_limit REAL,
                reason TEXT,
                status TEXT,
                assessed_by TEXT DEFAULT 'credit-assessment-agent'
            );
        """)

        # Seed if empty
        existing = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        if existing > 0:
            return

        # --- Seed customers ---
        _seed_data = [
            ("CUST-1001", "Alice Johnson", "alice.johnson@example.com", 780, 10000.00, 48, 95000.00, 1200.00, 0.35, 1, 0),
            ("CUST-1002", "Bob Martinez", "bob.martinez@example.com", 650, 5000.00, 18, 55000.00, 1800.00, 0.78, 4, 2),
            ("CUST-1003", "Carol Chen", "carol.chen@example.com", 720, 15000.00, 36, 120000.00, 2500.00, 0.52, 2, 1),
            ("CUST-1004", "David Park", "david.park@example.com", 820, 25000.00, 72, 150000.00, 3000.00, 0.22, 0, 0),
        ]
        conn.executemany(
            "INSERT INTO customers VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            _seed_data,
        )

        # --- Seed account balances ---
        _balances = [
            ("CUST-1001", 12450.00, 34200.00, 3500.00),
            ("CUST-1002", 2100.00, 800.00, 3900.00),
            ("CUST-1003", 28700.00, 15600.00, 7800.00),
            ("CUST-1004", 45300.00, 89000.00, 5500.00),
        ]
        now = datetime.now(timezone.utc).isoformat()
        conn.executemany(
            "INSERT INTO account_balances VALUES (?,?,?,?,?)",
            [(c, ck, sv, cr, now) for c, ck, sv, cr in _balances],
        )

        # --- Seed transactions ---
        _txns = [
            # Alice
            ("CUST-1001", "2026-02-25", "PURCHASE", "Amazon - Electronics", -289.99, 12160.01),
            ("CUST-1001", "2026-02-20", "PAYMENT", "Credit card payment", -2500.00, 12450.00),
            ("CUST-1001", "2026-02-15", "DEPOSIT", "Payroll direct deposit", 3958.33, 14950.00),
            ("CUST-1001", "2026-02-10", "PURCHASE", "Whole Foods", -156.42, 10991.67),
            ("CUST-1001", "2026-02-01", "PAYMENT", "Mortgage payment", -1800.00, 11148.09),
            # Bob
            ("CUST-1002", "2026-02-24", "PURCHASE", "Gas Station", -62.50, 2037.50),
            ("CUST-1002", "2026-02-18", "PAYMENT", "Minimum credit card payment", -150.00, 2100.00),
            ("CUST-1002", "2026-02-15", "DEPOSIT", "Payroll direct deposit", 2291.67, 2250.00),
            ("CUST-1002", "2026-02-05", "WITHDRAWAL", "ATM Withdrawal", -200.00, -41.67),
            ("CUST-1002", "2026-02-01", "PURCHASE", "Best Buy - TV", -899.99, 158.33),
            # Carol
            ("CUST-1003", "2026-02-26", "PURCHASE", "Delta Airlines - Flight", -487.00, 28213.00),
            ("CUST-1003", "2026-02-22", "PAYMENT", "Credit card full payment", -4200.00, 28700.00),
            ("CUST-1003", "2026-02-15", "DEPOSIT", "Payroll direct deposit", 5000.00, 32900.00),
            ("CUST-1003", "2026-02-08", "TRANSFER", "Transfer to savings", -2000.00, 27900.00),
            ("CUST-1003", "2026-02-01", "PAYMENT", "Rent payment", -3200.00, 29900.00),
            # David
            ("CUST-1004", "2026-02-25", "PURCHASE", "Tesla Supercharger", -18.50, 45281.50),
            ("CUST-1004", "2026-02-20", "PAYMENT", "Credit card full payment", -5500.00, 45300.00),
            ("CUST-1004", "2026-02-15", "DEPOSIT", "Payroll direct deposit", 6250.00, 50800.00),
            ("CUST-1004", "2026-02-10", "INVESTMENT", "Brokerage transfer", -5000.00, 44550.00),
            ("CUST-1004", "2026-02-01", "PAYMENT", "Mortgage payment", -3500.00, 49550.00),
        ]
        conn.executemany(
            "INSERT INTO transactions (customer_id, timestamp, type, description, amount, balance_after) VALUES (?,?,?,?,?,?)",
            _txns,
        )

        # --- Seed payment history ---
        _payments = [
            # Alice - perfect history
            ("CUST-1001", "2025-12", 2500, 2500, 1), ("CUST-1001", "2025-11", 3100, 3100, 1),
            ("CUST-1001", "2025-10", 1800, 1800, 1), ("CUST-1001", "2025-09", 2200, 2200, 1),
            ("CUST-1001", "2025-08", 2700, 2700, 1), ("CUST-1001", "2025-07", 1900, 1900, 1),
            # Bob - missed payments
            ("CUST-1002", "2025-12", 1500, 1500, 1), ("CUST-1002", "2025-11", 1200, 1000, 0),
            ("CUST-1002", "2025-10", 1800, 1800, 1), ("CUST-1002", "2025-09", 900, 900, 1),
            ("CUST-1002", "2025-08", 2100, 1500, 0), ("CUST-1002", "2025-07", 1100, 1100, 1),
            # Carol - one late
            ("CUST-1003", "2025-12", 4200, 4200, 1), ("CUST-1003", "2025-11", 3800, 3800, 1),
            ("CUST-1003", "2025-10", 5100, 5100, 1), ("CUST-1003", "2025-09", 2900, 2900, 1),
            ("CUST-1003", "2025-08", 3500, 3000, 0), ("CUST-1003", "2025-07", 4000, 4000, 1),
            # David - perfect history
            ("CUST-1004", "2025-12", 5500, 5500, 1), ("CUST-1004", "2025-11", 4800, 4800, 1),
            ("CUST-1004", "2025-10", 6200, 6200, 1), ("CUST-1004", "2025-09", 3900, 3900, 1),
            ("CUST-1004", "2025-08", 5100, 5100, 1), ("CUST-1004", "2025-07", 4500, 4500, 1),
        ]
        conn.executemany(
            "INSERT INTO payment_history (customer_id, month, amount_due, amount_paid, on_time) VALUES (?,?,?,?,?)",
            _payments,
        )


# ---------------------------------------------------------------------------
# Query helpers (used by tools)
# ---------------------------------------------------------------------------

def get_customer(customer_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        return dict(row) if row else None


def get_all_customer_ids() -> list[str]:
    with get_db() as conn:
        return [r[0] for r in conn.execute("SELECT id FROM customers").fetchall()]


def get_balances(customer_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM account_balances WHERE customer_id = ?", (customer_id,)).fetchone()
        return dict(row) if row else None


def get_transactions(customer_id: str, limit: int = 10) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE customer_id = ? ORDER BY timestamp DESC LIMIT ?",
            (customer_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_payment_history_rows(customer_id: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM payment_history WHERE customer_id = ? ORDER BY month DESC",
            (customer_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def update_credit_limit_db(customer_id: str, old_limit: float, new_limit: float, reason: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            "UPDATE customers SET current_credit_limit = ? WHERE id = ?",
            (new_limit, customer_id),
        )
        conn.execute(
            "INSERT INTO credit_limit_changes (customer_id, timestamp, old_limit, new_limit, reason, status) VALUES (?,?,?,?,?,?)",
            (customer_id, now, old_limit, new_limit, reason, "APPLIED"),
        )
        conn.execute(
            "INSERT INTO transactions (customer_id, timestamp, type, description, amount, balance_after) VALUES (?,?,?,?,?,?)",
            (customer_id, now, "CREDIT_LIMIT_CHANGE", f"Credit limit increased: {reason}", 0, new_limit),
        )
    return {"timestamp": now, "old_limit": old_limit, "new_limit": new_limit}


def get_credit_limit_history(customer_id: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM credit_limit_changes WHERE customer_id = ? ORDER BY timestamp DESC",
            (customer_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# Initialize on import
init_db()
