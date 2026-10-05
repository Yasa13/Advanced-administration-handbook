from pathlib import Path
import sqlite3

from app import db
from app.bank import search_open_invoices, score_candidate


def _setup_temp_db(tmp_path, monkeypatch):
    path = tmp_path / "finora.db"
    monkeypatch.setattr(db, "DB_PATH", path)
    db.init_db()
    return path


def _insert_invoice_and_tx(path: Path, *, gross="100,00", doc_type="Ausgangsrechnung", tx_amount=100.0):
    con = sqlite3.connect(path)
    con.execute("INSERT INTO documents (original_filename) VALUES ('rechnung.pdf')")
    doc_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    con.execute(
        """INSERT INTO classifications
           (document_id, document_type, correspondent, document_date, invoice_number, gross_amount, title, user_confirmed)
           VALUES (?,?,?,?,?,?,?,1)""",
        (doc_id, doc_type, "Kunde GmbH", "2026-08-01", "RG-100", gross, "Testrechnung"),
    )
    con.execute(
        """INSERT INTO bank_transactions
           (booking_date, participant_name, purpose, amount, currency, row_hash)
           VALUES ('2026-08-18','Kunde GmbH','RG-100',?,'EUR',?)""",
        (tx_amount, f"hash-{tx_amount}-{doc_id}"),
    )
    tx_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    con.commit()
    con.close()
    return int(doc_id), int(tx_id)


def test_partial_payment_keeps_transaction_open(tmp_path, monkeypatch):
    path = _setup_temp_db(tmp_path, monkeypatch)
    doc_id, tx_id = _insert_invoice_and_tx(path, gross="100,00", tx_amount=60.0)
    result = db.confirm_payment_match(tx_id, doc_id, 60.0, 0.9)
    assert result["status"] == "Teilbezahlt"
    assert round(result["remaining"], 2) == 40.00
    assert result["transaction_status"] == "Zugeordnet"
    assert round(result["transaction_remaining"], 2) == 0.00


def test_collective_payment_can_match_two_invoices(tmp_path, monkeypatch):
    path = _setup_temp_db(tmp_path, monkeypatch)
    doc1, tx_id = _insert_invoice_and_tx(path, gross="60,00", tx_amount=100.0)
    con = sqlite3.connect(path)
    con.execute("INSERT INTO documents (original_filename) VALUES ('rechnung2.pdf')")
    doc2 = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    con.execute(
        """INSERT INTO classifications
           (document_id, document_type, correspondent, document_date, invoice_number, gross_amount, title, user_confirmed)
           VALUES (?,?,?,?,?,?,?,1)""",
        (doc2, "Ausgangsrechnung", "Kunde GmbH", "2026-08-02", "RG-101", "40,00", "Testrechnung 2"),
    )
    con.commit(); con.close()
    first = db.confirm_payment_match(tx_id, doc1, 60.0, 0.9)
    assert first["transaction_status"] == "Teilzugeordnet"
    assert round(first["transaction_remaining"], 2) == 40.0
    second = db.confirm_payment_match(tx_id, int(doc2), 40.0, 0.9)
    assert second["transaction_status"] == "Zugeordnet"
    assert round(second["transaction_remaining"], 2) == 0.0


def test_unmatch_reopens_invoice_and_transaction(tmp_path, monkeypatch):
    path = _setup_temp_db(tmp_path, monkeypatch)
    doc_id, tx_id = _insert_invoice_and_tx(path, gross="100,00", tx_amount=100.0)
    db.confirm_payment_match(tx_id, doc_id, 100.0, 0.9)
    con = sqlite3.connect(path)
    match_id = con.execute("SELECT id FROM payment_matches").fetchone()[0]
    con.close()
    db.remove_payment_match(match_id)
    con = sqlite3.connect(path)
    status, open_amount = con.execute("SELECT payment_status, open_amount FROM classifications WHERE document_id=?", (doc_id,)).fetchone()
    tx_status = con.execute("SELECT reconciliation_status FROM bank_transactions WHERE id=?", (tx_id,)).fetchone()[0]
    con.close()
    assert status == "Offen"
    assert round(open_amount, 2) == 100.0
    assert tx_status == "Offen"


def test_manual_search_by_invoice_number(tmp_path, monkeypatch):
    path = _setup_temp_db(tmp_path, monkeypatch)
    doc_id, tx_id = _insert_invoice_and_tx(path, gross="100,00", tx_amount=100.0)
    tx = db.list_bank_transactions()[0]
    results = search_open_invoices(tx, "RG-100")
    assert results
    assert results[0]["document_id"] == doc_id


def test_score_collective_payment_mentions_collective():
    tx = {"amount": 100.0, "remaining_amount": 100.0, "purpose": "", "booking_text": "", "participant_name": "Kunde GmbH"}
    candidate = {"open_amount": 60.0, "gross_amount": "60,00", "invoice_number": "RG-1", "correspondent": "Kunde GmbH", "document_type": "Ausgangsrechnung"}
    score, reasons = score_candidate(tx, candidate)
    assert score > 0
    assert any("Sammelzahlung" in r for r in reasons)
