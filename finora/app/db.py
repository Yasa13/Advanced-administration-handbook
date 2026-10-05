from __future__ import annotations

import sqlite3
from typing import Any

from .config import DB_PATH


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def _ensure_column(cur: sqlite3.Cursor, table: str, column: str, definition: str) -> None:
    columns = {row[1] for row in cur.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = _connect()
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_filename TEXT NOT NULL,
        stored_filename TEXT,
        original_copy_path TEXT,
        file_path TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS classifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER,
        document_type TEXT,
        correspondent TEXT,
        addressee_type TEXT,
        addressee_name TEXT,
        private_person TEXT,
        document_date TEXT,
        invoice_number TEXT,
        gross_amount TEXT,
        title TEXT,
        target_folder TEXT,
        confidence_document_type REAL,
        confidence_correspondent REAL,
        confidence_addressee REAL,
        user_confirmed INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS learning_examples (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER,
        feature_type TEXT,
        feature_value TEXT,
        predicted_value TEXT,
        confirmed_value TEXT,
        was_correct INTEGER,
        confidence_before REAL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS learned_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rule_type TEXT,
        feature TEXT,
        target_value TEXT,
        weight REAL DEFAULT 0.1,
        confirmations INTEGER DEFAULT 0,
        corrections INTEGER DEFAULT 0,
        last_used TEXT,
        active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS learning_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER,
        ocr_text TEXT NOT NULL,
        document_type TEXT,
        correspondent TEXT,
        addressee_type TEXT,
        private_person TEXT,
        document_type_weight REAL DEFAULT 1.0,
        correspondent_weight REAL DEFAULT 1.0,
        addressee_type_weight REAL DEFAULT 1.0,
        private_person_weight REAL DEFAULT 1.0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS bank_imports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        account_name TEXT,
        account_iban TEXT,
        bank_name TEXT,
        imported_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS bank_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        import_id INTEGER,
        booking_date TEXT,
        value_date TEXT,
        participant_name TEXT,
        participant_iban TEXT,
        booking_text TEXT,
        purpose TEXT,
        amount REAL NOT NULL,
        currency TEXT,
        balance REAL,
        category TEXT,
        source_row INTEGER,
        row_hash TEXT UNIQUE,
        reconciliation_status TEXT DEFAULT 'Offen',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS payment_matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_id INTEGER NOT NULL,
        document_id INTEGER NOT NULL,
        matched_amount REAL NOT NULL,
        confidence REAL DEFAULT 0,
        confirmed_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    _ensure_column(cur, "classifications", "private_person", "TEXT")
    _ensure_column(cur, "learning_documents", "document_type_weight", "REAL DEFAULT 1.0")
    _ensure_column(cur, "learning_documents", "correspondent_weight", "REAL DEFAULT 1.0")
    _ensure_column(cur, "learning_documents", "addressee_type_weight", "REAL DEFAULT 1.0")
    _ensure_column(cur, "learning_documents", "private_person_weight", "REAL DEFAULT 1.0")
    _ensure_column(cur, "classifications", "payment_status", "TEXT DEFAULT 'Offen'")
    _ensure_column(cur, "classifications", "open_amount", "REAL")
    _ensure_column(cur, "classifications", "payment_date", "TEXT")
    con.commit()
    con.close()


def log_document(
    original_filename: str,
    stored_filename: str,
    original_copy_path: str,
    file_path: str,
    classification: dict,
) -> int:
    con = _connect()
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO documents (original_filename, stored_filename, original_copy_path, file_path)
        VALUES (?, ?, ?, ?)
        """,
        (original_filename, stored_filename, original_copy_path, file_path),
    )
    document_id = int(cur.lastrowid)
    cur.execute(
        """
        INSERT INTO classifications (
            document_id, document_type, correspondent, addressee_type, addressee_name,
            private_person, document_date, invoice_number, gross_amount, title, target_folder,
            confidence_document_type, confidence_correspondent, confidence_addressee,
            user_confirmed
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (
            document_id,
            classification.get("document_type", ""),
            classification.get("correspondent", ""),
            classification.get("addressee_type", ""),
            classification.get("addressee_name", ""),
            classification.get("private_person", ""),
            classification.get("document_date", ""),
            classification.get("invoice_number", ""),
            classification.get("gross_amount", ""),
            classification.get("title", ""),
            classification.get("target_folder", ""),
            classification.get("confidence_document_type", 0.0),
            classification.get("confidence_correspondent", 0.0),
            classification.get("confidence_addressee", 0.0),
        ),
    )
    con.commit()
    con.close()
    return document_id


def record_learning(
    document_id: int,
    ocr_text: str,
    confirmed: dict[str, str],
    predicted: dict[str, str],
    confidences: dict[str, float],
) -> None:
    con = _connect()
    cur = con.cursor()
    weights = {}
    for field in ("document_type", "correspondent", "addressee_type", "private_person"):
        confirmed_value = (confirmed.get(field, "") or "").strip()
        predicted_value = (predicted.get(field, "") or "").strip()
        # Explicit corrections teach more strongly than unchanged confirmations.
        weights[field] = 1.35 if confirmed_value and predicted_value and confirmed_value != predicted_value else 1.0

    cur.execute(
        """
        INSERT INTO learning_documents (
            document_id, ocr_text, document_type, correspondent, addressee_type, private_person,
            document_type_weight, correspondent_weight, addressee_type_weight, private_person_weight
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            document_id,
            ocr_text,
            confirmed.get("document_type", ""),
            confirmed.get("correspondent", ""),
            confirmed.get("addressee_type", ""),
            confirmed.get("private_person", ""),
            weights["document_type"],
            weights["correspondent"],
            weights["addressee_type"],
            weights["private_person"],
        ),
    )
    for field in ("document_type", "correspondent", "addressee_type", "private_person"):
        p = predicted.get(field, "")
        c = confirmed.get(field, "")
        if not c:
            continue
        cur.execute(
            """
            INSERT INTO learning_examples (
                document_id, feature_type, feature_value, predicted_value, confirmed_value,
                was_correct, confidence_before
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                field,
                "ocr_similarity",
                p,
                c,
                int(p == c),
                float(confidences.get(field, 0.0)),
            ),
        )
    con.commit()
    con.close()


def get_learning_documents(limit: int = 500) -> list[dict[str, Any]]:
    if not DB_PATH.exists():
        return []
    con = _connect()
    try:
        rows = con.execute(
            """
            SELECT document_id, ocr_text, document_type, correspondent, addressee_type, private_person,
                   document_type_weight, correspondent_weight, addressee_type_weight, private_person_weight
            FROM learning_documents
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        con.close()



def create_bank_import(filename: str, meta: dict[str, str]) -> int:
    con = _connect()
    cur = con.cursor()
    cur.execute(
        """INSERT INTO bank_imports (filename, account_name, account_iban, bank_name)
           VALUES (?, ?, ?, ?)""",
        (filename, meta.get("account_name", ""), meta.get("account_iban", ""), meta.get("bank_name", "")),
    )
    import_id = int(cur.lastrowid)
    con.commit()
    con.close()
    return import_id


def insert_bank_transaction(import_id: int, tx: Any) -> bool:
    con = _connect()
    try:
        con.execute(
            """INSERT INTO bank_transactions (
                import_id, booking_date, value_date, participant_name, participant_iban,
                booking_text, purpose, amount, currency, balance, category, source_row, row_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                import_id,
                tx.booking_date,
                tx.value_date,
                tx.participant_name,
                tx.participant_iban,
                tx.booking_text,
                tx.purpose,
                float(tx.amount),
                tx.currency,
                None if tx.balance is None else float(tx.balance),
                tx.category,
                tx.source_row,
                tx.row_hash,
            ),
        )
        con.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        con.close()


def list_bank_transactions(limit: int = 250) -> list[dict[str, Any]]:
    con = _connect()
    rows = con.execute(
        """SELECT * FROM bank_transactions
           ORDER BY booking_date DESC, id DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        matched = con.execute(
            "SELECT COALESCE(SUM(matched_amount), 0) FROM payment_matches WHERE transaction_id=?",
            (item["id"],),
        ).fetchone()[0]
        item["matched_amount"] = float(matched or 0.0)
        item["remaining_amount"] = max(0.0, abs(float(item.get("amount") or 0.0)) - item["matched_amount"])
        match_rows = con.execute(
            """SELECT pm.id AS match_id, pm.document_id, pm.matched_amount, pm.confidence, pm.confirmed_at,
                      c.document_type, c.correspondent, c.invoice_number, c.gross_amount, c.payment_status, c.open_amount
               FROM payment_matches pm
               LEFT JOIN classifications c ON c.document_id = pm.document_id
               WHERE pm.transaction_id=?
               ORDER BY pm.id""",
            (item["id"],),
        ).fetchall()
        item["matches"] = [dict(r) for r in match_rows]
        result.append(item)
    con.close()
    return result


def get_open_invoice_candidates() -> list[dict[str, Any]]:
    con = _connect()
    rows = con.execute(
        """SELECT c.*, d.original_filename, d.stored_filename, d.file_path
           FROM classifications c
           JOIN documents d ON d.id = c.document_id
           WHERE c.document_type IN ('Eingangsrechnung','Ausgangsrechnung')
             AND COALESCE(c.payment_status, 'Offen') != 'Bezahlt'
           ORDER BY c.document_date DESC, c.id DESC"""
    ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        if d.get("open_amount") is None:
            raw = (d.get("gross_amount") or "").replace(".", "").replace(",", ".")
            try:
                d["open_amount"] = float(raw)
            except ValueError:
                d["open_amount"] = 0.0
        result.append(d)
    con.close()
    return result


def _invoice_gross(row: sqlite3.Row | dict[str, Any]) -> float:
    raw = str(row["gross_amount"] or "").replace(".", "").replace(",", ".")
    try:
        return abs(float(raw))
    except ValueError:
        return 0.0


def _recompute_invoice(con: sqlite3.Connection, document_id: int) -> dict[str, Any]:
    cl = con.execute(
        "SELECT * FROM classifications WHERE document_id=? ORDER BY id DESC LIMIT 1",
        (document_id,),
    ).fetchone()
    if not cl:
        raise ValueError("Rechnung nicht gefunden.")
    gross = _invoice_gross(cl)
    payment_row = con.execute(
        """SELECT COALESCE(SUM(pm.matched_amount),0) AS paid, MAX(bt.booking_date) AS last_date
           FROM payment_matches pm
           JOIN bank_transactions bt ON bt.id=pm.transaction_id
           WHERE pm.document_id=?""",
        (document_id,),
    ).fetchone()
    paid = abs(float(payment_row["paid"] or 0.0))
    remaining = max(0.0, gross - paid)
    if paid <= 0.01:
        status = "Offen"
        payment_date = None
    elif remaining <= 0.01:
        status = "Bezahlt"
        payment_date = payment_row["last_date"]
    else:
        status = "Teilbezahlt"
        payment_date = payment_row["last_date"]
    con.execute(
        "UPDATE classifications SET payment_status=?, open_amount=?, payment_date=? WHERE document_id=?",
        (status, remaining, payment_date, document_id),
    )
    return {"status": status, "remaining": remaining, "payment_date": payment_date, "paid": paid}


def _recompute_transaction(con: sqlite3.Connection, transaction_id: int) -> dict[str, Any]:
    tx = con.execute("SELECT * FROM bank_transactions WHERE id=?", (transaction_id,)).fetchone()
    if not tx:
        raise ValueError("Bankbuchung nicht gefunden.")
    matched = con.execute(
        "SELECT COALESCE(SUM(matched_amount),0) FROM payment_matches WHERE transaction_id=?",
        (transaction_id,),
    ).fetchone()[0]
    matched = abs(float(matched or 0.0))
    total = abs(float(tx["amount"] or 0.0))
    remaining = max(0.0, total - matched)
    if matched <= 0.01:
        status = "Offen"
    elif remaining <= 0.01:
        status = "Zugeordnet"
    else:
        status = "Teilzugeordnet"
    con.execute("UPDATE bank_transactions SET reconciliation_status=? WHERE id=?", (status, transaction_id))
    return {"status": status, "matched": matched, "remaining": remaining}


def confirm_payment_match(transaction_id: int, document_id: int, amount: float, confidence: float = 0.0) -> dict[str, Any]:
    con = _connect()
    try:
        tx = con.execute("SELECT * FROM bank_transactions WHERE id=?", (transaction_id,)).fetchone()
        cl = con.execute("SELECT * FROM classifications WHERE document_id=? ORDER BY id DESC LIMIT 1", (document_id,)).fetchone()
        if not tx or not cl:
            raise ValueError("Bankbuchung oder Rechnung nicht gefunden.")

        tx_state = _recompute_transaction(con, transaction_id)
        invoice_state = _recompute_invoice(con, document_id)
        requested = abs(float(amount))
        allocatable = min(requested, tx_state["remaining"], invoice_state["remaining"])
        if allocatable <= 0.005:
            raise ValueError("Für diese Zuordnung ist kein offener Betrag mehr vorhanden.")

        con.execute(
            """INSERT INTO payment_matches (transaction_id, document_id, matched_amount, confidence)
               VALUES (?, ?, ?, ?)""",
            (transaction_id, document_id, allocatable, confidence),
        )
        invoice_state = _recompute_invoice(con, document_id)
        tx_state = _recompute_transaction(con, transaction_id)
        con.commit()
        return {
            "status": invoice_state["status"],
            "remaining": invoice_state["remaining"],
            "payment_date": invoice_state["payment_date"],
            "transaction_status": tx_state["status"],
            "transaction_remaining": tx_state["remaining"],
            "matched_amount": allocatable,
        }
    finally:
        con.close()


def remove_payment_match(match_id: int) -> dict[str, Any]:
    con = _connect()
    try:
        row = con.execute(
            "SELECT transaction_id, document_id FROM payment_matches WHERE id=?",
            (match_id,),
        ).fetchone()
        if not row:
            raise ValueError("Zuordnung nicht gefunden.")
        transaction_id = int(row["transaction_id"])
        document_id = int(row["document_id"])
        con.execute("DELETE FROM payment_matches WHERE id=?", (match_id,))
        invoice_state = _recompute_invoice(con, document_id)
        tx_state = _recompute_transaction(con, transaction_id)
        con.commit()
        return {"invoice": invoice_state, "transaction": tx_state}
    finally:
        con.close()
