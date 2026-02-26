"""SQLite database for Solo Bank — accounts, balances, transactions, transfers."""

import os
import sqlite3
from datetime import datetime, timezone
from contextlib import contextmanager

DB_PATH = os.environ.get("BANK_DB_PATH", "/data/bank.db")


def _get_db_path() -> str:
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and os.path.isdir(db_dir):
        return DB_PATH
    return os.path.join(os.path.dirname(__file__), "bank.db")


_DB = _get_db_path()


@contextmanager
def get_db():
    conn = sqlite3.connect(_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS customers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT,
                pin TEXT DEFAULT '1234',
                credit_score INTEGER,
                current_credit_limit REAL,
                account_age_months INTEGER,
                annual_income REAL,
                monthly_debt_payments REAL,
                utilization_rate REAL,
                recent_inquiries INTEGER DEFAULT 0,
                delinquencies_last_2y INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                customer_id TEXT REFERENCES customers(id),
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                balance REAL DEFAULT 0,
                currency TEXT DEFAULT 'USD'
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT REFERENCES accounts(id),
                customer_id TEXT REFERENCES customers(id),
                timestamp TEXT NOT NULL,
                type TEXT NOT NULL,
                description TEXT,
                amount REAL NOT NULL,
                balance_after REAL,
                related_account_id TEXT
            );

            CREATE TABLE IF NOT EXISTS transfers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_account_id TEXT REFERENCES accounts(id),
                to_account_id TEXT REFERENCES accounts(id),
                amount REAL NOT NULL,
                description TEXT,
                timestamp TEXT NOT NULL,
                status TEXT DEFAULT 'COMPLETED'
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

            CREATE TABLE IF NOT EXISTS payment_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT REFERENCES customers(id),
                month TEXT NOT NULL,
                amount_due REAL,
                amount_paid REAL,
                on_time INTEGER
            );

            CREATE TABLE IF NOT EXISTS pending_approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT REFERENCES customers(id),
                type TEXT NOT NULL,
                description TEXT,
                amount REAL,
                timestamp TEXT NOT NULL,
                status TEXT DEFAULT 'PENDING',
                resolved_at TEXT,
                resolved_by TEXT
            );
        """)

        existing = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        if existing > 0:
            return

        now = datetime.now(timezone.utc).isoformat()

        # --- Customers ---
        customers = [
            ("CUST-1001", "Alice Johnson", "alice.johnson@solobank.com", "1234", 780, 10000, 48, 95000, 1200, 0.35, 1, 0),
            ("CUST-1002", "Bob Martinez", "bob.martinez@solobank.com", "1234", 650, 5000, 18, 55000, 1800, 0.78, 4, 2),
            ("CUST-1003", "Carol Chen", "carol.chen@solobank.com", "1234", 720, 15000, 36, 120000, 2500, 0.52, 2, 1),
            ("CUST-1004", "David Park", "david.park@solobank.com", "1234", 820, 25000, 72, 150000, 3000, 0.22, 0, 0),
        ]
        conn.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", customers)

        # --- Accounts ---
        accounts = [
            ("ACC-1001-CHK", "CUST-1001", "checking", "Checking Account", 12450.00, "USD"),
            ("ACC-1001-SAV", "CUST-1001", "savings", "Savings Account", 34200.00, "USD"),
            ("ACC-1001-CRD", "CUST-1001", "credit", "Platinum Credit Card", -3500.00, "USD"),

            ("ACC-1002-CHK", "CUST-1002", "checking", "Checking Account", 2100.00, "USD"),
            ("ACC-1002-SAV", "CUST-1002", "savings", "Savings Account", 800.00, "USD"),
            ("ACC-1002-CRD", "CUST-1002", "credit", "Gold Credit Card", -3900.00, "USD"),

            ("ACC-1003-CHK", "CUST-1003", "checking", "Checking Account", 28700.00, "USD"),
            ("ACC-1003-SAV", "CUST-1003", "savings", "Savings Account", 15600.00, "USD"),
            ("ACC-1003-CRD", "CUST-1003", "credit", "Platinum Credit Card", -7800.00, "USD"),

            ("ACC-1004-CHK", "CUST-1004", "checking", "Checking Account", 45300.00, "USD"),
            ("ACC-1004-SAV", "CUST-1004", "savings", "Savings Account", 89000.00, "USD"),
            ("ACC-1004-CRD", "CUST-1004", "credit", "Black Credit Card", -5500.00, "USD"),
        ]
        conn.executemany("INSERT INTO accounts VALUES (?,?,?,?,?,?)", accounts)

        # --- Transactions ---
        txns = [
            ("ACC-1001-CHK", "CUST-1001", "2026-02-25T14:30:00Z", "PURCHASE", "Amazon - Electronics", -289.99, 12160.01, None),
            ("ACC-1001-CHK", "CUST-1001", "2026-02-20T09:00:00Z", "PAYMENT", "Credit card payment", -2500.00, 12450.00, "ACC-1001-CRD"),
            ("ACC-1001-CHK", "CUST-1001", "2026-02-15T08:00:00Z", "DEPOSIT", "Payroll - TechCorp Inc", 3958.33, 14950.00, None),
            ("ACC-1001-CHK", "CUST-1001", "2026-02-10T12:15:00Z", "PURCHASE", "Whole Foods Market", -156.42, 10991.67, None),
            ("ACC-1001-CHK", "CUST-1001", "2026-02-01T08:00:00Z", "PAYMENT", "Mortgage payment", -1800.00, 11148.09, None),
            ("ACC-1001-SAV", "CUST-1001", "2026-02-15T08:05:00Z", "DEPOSIT", "Auto-save from checking", 500.00, 34200.00, "ACC-1001-CHK"),

            ("ACC-1002-CHK", "CUST-1002", "2026-02-24T16:45:00Z", "PURCHASE", "Shell Gas Station", -62.50, 2037.50, None),
            ("ACC-1002-CHK", "CUST-1002", "2026-02-18T10:00:00Z", "PAYMENT", "Minimum CC payment", -150.00, 2100.00, "ACC-1002-CRD"),
            ("ACC-1002-CHK", "CUST-1002", "2026-02-15T08:00:00Z", "DEPOSIT", "Payroll - RetailMax", 2291.67, 2250.00, None),
            ("ACC-1002-CHK", "CUST-1002", "2026-02-05T14:20:00Z", "WITHDRAWAL", "ATM Withdrawal", -200.00, -41.67, None),
            ("ACC-1002-CRD", "CUST-1002", "2026-02-01T11:30:00Z", "PURCHASE", "Best Buy - 65\" TV", -899.99, -3900.00, None),

            ("ACC-1003-CHK", "CUST-1003", "2026-02-26T09:10:00Z", "PURCHASE", "Delta Airlines - SFO to JFK", -487.00, 28213.00, None),
            ("ACC-1003-CHK", "CUST-1003", "2026-02-22T10:00:00Z", "PAYMENT", "Credit card full payment", -4200.00, 28700.00, "ACC-1003-CRD"),
            ("ACC-1003-CHK", "CUST-1003", "2026-02-15T08:00:00Z", "DEPOSIT", "Payroll - Acme Corp", 5000.00, 32900.00, None),
            ("ACC-1003-CHK", "CUST-1003", "2026-02-08T15:30:00Z", "TRANSFER", "Transfer to savings", -2000.00, 27900.00, "ACC-1003-SAV"),
            ("ACC-1003-SAV", "CUST-1003", "2026-02-08T15:30:00Z", "TRANSFER", "Transfer from checking", 2000.00, 15600.00, "ACC-1003-CHK"),

            ("ACC-1004-CHK", "CUST-1004", "2026-02-25T07:30:00Z", "PURCHASE", "Tesla Supercharger", -18.50, 45281.50, None),
            ("ACC-1004-CHK", "CUST-1004", "2026-02-20T10:00:00Z", "PAYMENT", "Credit card full payment", -5500.00, 45300.00, "ACC-1004-CRD"),
            ("ACC-1004-CHK", "CUST-1004", "2026-02-15T08:00:00Z", "DEPOSIT", "Payroll - FinanceHub", 6250.00, 50800.00, None),
            ("ACC-1004-CHK", "CUST-1004", "2026-02-10T11:00:00Z", "TRANSFER", "Brokerage transfer", -5000.00, 44550.00, None),
        ]
        conn.executemany(
            "INSERT INTO transactions (account_id,customer_id,timestamp,type,description,amount,balance_after,related_account_id) VALUES (?,?,?,?,?,?,?,?)",
            txns,
        )

        # --- Payment history ---
        payments = [
            ("CUST-1001", "2025-12", 2500, 2500, 1), ("CUST-1001", "2025-11", 3100, 3100, 1),
            ("CUST-1001", "2025-10", 1800, 1800, 1), ("CUST-1001", "2025-09", 2200, 2200, 1),
            ("CUST-1001", "2025-08", 2700, 2700, 1), ("CUST-1001", "2025-07", 1900, 1900, 1),
            ("CUST-1002", "2025-12", 1500, 1500, 1), ("CUST-1002", "2025-11", 1200, 1000, 0),
            ("CUST-1002", "2025-10", 1800, 1800, 1), ("CUST-1002", "2025-09", 900, 900, 1),
            ("CUST-1002", "2025-08", 2100, 1500, 0), ("CUST-1002", "2025-07", 1100, 1100, 1),
            ("CUST-1003", "2025-12", 4200, 4200, 1), ("CUST-1003", "2025-11", 3800, 3800, 1),
            ("CUST-1003", "2025-10", 5100, 5100, 1), ("CUST-1003", "2025-09", 2900, 2900, 1),
            ("CUST-1003", "2025-08", 3500, 3000, 0), ("CUST-1003", "2025-07", 4000, 4000, 1),
            ("CUST-1004", "2025-12", 5500, 5500, 1), ("CUST-1004", "2025-11", 4800, 4800, 1),
            ("CUST-1004", "2025-10", 6200, 6200, 1), ("CUST-1004", "2025-09", 3900, 3900, 1),
            ("CUST-1004", "2025-08", 5100, 5100, 1), ("CUST-1004", "2025-07", 4500, 4500, 1),
        ]
        conn.executemany("INSERT INTO payment_history (customer_id,month,amount_due,amount_paid,on_time) VALUES (?,?,?,?,?)", payments)

        # --- Seed some pending approvals ---
        approvals = [
            ("CUST-1002", "WIRE_TRANSFER", "Wire transfer to external account ending 4589", 3500.00, "2026-02-26T10:30:00Z", "PENDING"),
            ("CUST-1003", "LARGE_PURCHASE", "Purchase authorization: Luxury Auto Dealer", 28500.00, "2026-02-26T11:00:00Z", "PENDING"),
        ]
        conn.executemany(
            "INSERT INTO pending_approvals (customer_id,type,description,amount,timestamp,status) VALUES (?,?,?,?,?,?)",
            approvals,
        )


# ---- Query helpers ----

def get_customer(customer_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        return dict(row) if row else None


def get_all_customers() -> list[dict]:
    with get_db() as conn:
        return [dict(r) for r in conn.execute("SELECT id, name, email FROM customers").fetchall()]


def get_accounts(customer_id: str) -> list[dict]:
    with get_db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM accounts WHERE customer_id = ?", (customer_id,)).fetchall()]


def get_transactions(account_id: str, limit: int = 20) -> list[dict]:
    with get_db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM transactions WHERE account_id = ? ORDER BY timestamp DESC LIMIT ?",
            (account_id, limit),
        ).fetchall()]


def get_all_transactions(customer_id: str, limit: int = 30) -> list[dict]:
    with get_db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT t.*, a.name as account_name, a.type as account_type FROM transactions t "
            "JOIN accounts a ON t.account_id = a.id "
            "WHERE t.customer_id = ? ORDER BY t.timestamp DESC LIMIT ?",
            (customer_id, limit),
        ).fetchall()]


def transfer_funds(from_account_id: str, to_account_id: str, amount: float, description: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        from_acc = conn.execute("SELECT * FROM accounts WHERE id = ?", (from_account_id,)).fetchone()
        to_acc = conn.execute("SELECT * FROM accounts WHERE id = ?", (to_account_id,)).fetchone()

        if not from_acc or not to_acc:
            return {"error": "Account not found"}
        if from_acc["type"] == "credit":
            return {"error": "Cannot transfer from a credit card account"}
        if amount <= 0:
            return {"error": "Amount must be positive"}
        if from_acc["balance"] < amount:
            return {"error": f"Insufficient funds. Available: ${from_acc['balance']:,.2f}"}

        new_from = from_acc["balance"] - amount
        new_to = to_acc["balance"] + amount

        conn.execute("UPDATE accounts SET balance = ? WHERE id = ?", (new_from, from_account_id))
        conn.execute("UPDATE accounts SET balance = ? WHERE id = ?", (new_to, to_account_id))

        conn.execute(
            "INSERT INTO transactions (account_id,customer_id,timestamp,type,description,amount,balance_after,related_account_id) VALUES (?,?,?,?,?,?,?,?)",
            (from_account_id, from_acc["customer_id"], now, "TRANSFER", f"Transfer to {to_acc['name']}: {description}", -amount, new_from, to_account_id),
        )
        conn.execute(
            "INSERT INTO transactions (account_id,customer_id,timestamp,type,description,amount,balance_after,related_account_id) VALUES (?,?,?,?,?,?,?,?)",
            (to_account_id, to_acc["customer_id"], now, "TRANSFER", f"Transfer from {from_acc['name']}: {description}", amount, new_to, from_account_id),
        )
        conn.execute(
            "INSERT INTO transfers (from_account_id,to_account_id,amount,description,timestamp) VALUES (?,?,?,?,?)",
            (from_account_id, to_account_id, amount, description, now),
        )

    return {"status": "SUCCESS", "from_balance": new_from, "to_balance": new_to, "timestamp": now}


def get_pending_approvals(customer_id: str) -> list[dict]:
    with get_db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM pending_approvals WHERE customer_id = ? AND status = 'PENDING' ORDER BY timestamp DESC",
            (customer_id,),
        ).fetchall()]


def resolve_approval(approval_id: int, action: str, resolved_by: str = "customer") -> dict:
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        row = conn.execute("SELECT * FROM pending_approvals WHERE id = ?", (approval_id,)).fetchone()
        if not row:
            return {"error": "Approval not found"}
        if row["status"] != "PENDING":
            return {"error": f"Already resolved: {row['status']}"}

        status = "APPROVED" if action == "approve" else "DENIED"
        conn.execute(
            "UPDATE pending_approvals SET status = ?, resolved_at = ?, resolved_by = ? WHERE id = ?",
            (status, now, resolved_by, approval_id),
        )

        if status == "APPROVED":
            if row["type"] == "CREDIT_LIMIT_INCREASE":
                # Apply credit limit change
                result = update_credit_limit(
                    row["customer_id"], row["amount"],
                    f"Admin approved: {row['description']}", "admin",
                )
                if "error" in result:
                    return result
            else:
                # Execute the approved transaction (wire transfer, large purchase)
                checking = conn.execute(
                    "SELECT * FROM accounts WHERE customer_id = ? AND type = 'checking'",
                    (row["customer_id"],),
                ).fetchone()
                if checking:
                    new_balance = checking["balance"] - row["amount"]
                    conn.execute("UPDATE accounts SET balance = ? WHERE id = ?", (new_balance, checking["id"]))
                    conn.execute(
                        "INSERT INTO transactions (account_id,customer_id,timestamp,type,description,amount,balance_after) VALUES (?,?,?,?,?,?,?)",
                        (checking["id"], row["customer_id"], now, row["type"], f"Approved: {row['description']}", -row["amount"], new_balance),
                    )
        elif status == "DENIED" and row["type"] == "CREDIT_LIMIT_INCREASE":
            # Record denial in credit limit history
            conn.execute(
                "UPDATE credit_limit_changes SET status = 'DENIED' WHERE customer_id = ? AND new_limit = ? AND status = 'PENDING_REVIEW'",
                (row["customer_id"], row["amount"]),
            )

    return {"status": status, "approval_id": approval_id, "timestamp": now}


def get_all_pending_approvals() -> list[dict]:
    with get_db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT pa.*, c.name as customer_name FROM pending_approvals pa "
            "JOIN customers c ON pa.customer_id = c.id "
            "WHERE pa.status = 'PENDING' ORDER BY pa.timestamp DESC",
        ).fetchall()]


def create_credit_limit_approval(
    customer_id: str, requested_new_limit: float, current_limit: float,
    reason: str, assessment_summary: str,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        customer = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        if not customer:
            return {"error": "Customer not found"}

        description = (
            f"Credit limit increase: ${current_limit:,.2f} → ${requested_new_limit:,.2f}. "
            f"Reason: {reason}. Assessment: {assessment_summary}"
        )
        conn.execute(
            "INSERT INTO pending_approvals (customer_id,type,description,amount,timestamp,status) VALUES (?,?,?,?,?,?)",
            (customer_id, "CREDIT_LIMIT_INCREASE", description, requested_new_limit, now, "PENDING"),
        )
        approval_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Record in credit_limit_changes as PENDING
        conn.execute(
            "INSERT INTO credit_limit_changes (customer_id,timestamp,old_limit,new_limit,reason,status,assessed_by) VALUES (?,?,?,?,?,?,?)",
            (customer_id, now, current_limit, requested_new_limit, reason, "PENDING_REVIEW", "credit-assessment-agent"),
        )

    return {
        "status": "PENDING_REVIEW",
        "approval_id": approval_id,
        "customer_id": customer_id,
        "requested_limit": requested_new_limit,
        "message": f"Request submitted for admin review (approval #{approval_id})",
    }


def get_credit_limit_history(customer_id: str) -> list[dict]:
    with get_db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM credit_limit_changes WHERE customer_id = ? ORDER BY timestamp DESC",
            (customer_id,),
        ).fetchall()]


def update_credit_limit(customer_id: str, new_limit: float, reason: str, assessed_by: str = "credit-assessment-agent") -> dict:
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        customer = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        if not customer:
            return {"error": "Customer not found"}

        old_limit = customer["current_credit_limit"]
        if new_limit <= old_limit:
            return {"error": f"New limit (${new_limit:,.2f}) must be higher than current limit (${old_limit:,.2f})"}
        if new_limit > old_limit * 3:
            return {"error": f"Cannot increase by more than 3x. Current: ${old_limit:,.2f}, Max: ${old_limit * 3:,.2f}"}

        conn.execute("UPDATE customers SET current_credit_limit = ? WHERE id = ?", (new_limit, customer_id))

        # Update utilization rate based on new limit
        credit_acc = conn.execute(
            "SELECT * FROM accounts WHERE customer_id = ? AND type = 'credit'", (customer_id,)
        ).fetchone()
        if credit_acc:
            new_util = abs(credit_acc["balance"]) / new_limit if new_limit > 0 else 0
            conn.execute("UPDATE customers SET utilization_rate = ? WHERE id = ?", (round(new_util, 4), customer_id))

        conn.execute(
            "INSERT INTO credit_limit_changes (customer_id,timestamp,old_limit,new_limit,reason,status,assessed_by) VALUES (?,?,?,?,?,?,?)",
            (customer_id, now, old_limit, new_limit, reason, "APPROVED", assessed_by),
        )

        # Record as a transaction on the credit account
        if credit_acc:
            conn.execute(
                "INSERT INTO transactions (account_id,customer_id,timestamp,type,description,amount,balance_after) VALUES (?,?,?,?,?,?,?)",
                (credit_acc["id"], customer_id, now, "CREDIT_LIMIT_CHANGE",
                 f"Credit limit increased: ${old_limit:,.2f} → ${new_limit:,.2f} ({reason})",
                 new_limit - old_limit, credit_acc["balance"]),
            )

    return {
        "status": "SUCCESS",
        "customer_id": customer_id,
        "previous_limit": old_limit,
        "new_limit": new_limit,
        "increase_amount": new_limit - old_limit,
        "reason": reason,
        "assessed_by": assessed_by,
        "timestamp": now,
    }


init_db()
