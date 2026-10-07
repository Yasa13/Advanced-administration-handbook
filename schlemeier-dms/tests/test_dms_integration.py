from __future__ import annotations

import importlib
import os
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "schlemeier-dms" / "backend"
FINORA = ROOT / "finora"
for path in (str(BACKEND), str(FINORA)):
    if path not in sys.path:
        sys.path.insert(0, path)


def load_services(tmp_path: Path):
    os.environ["FINORA_ROOT"] = str(tmp_path / "Finora")
    for name in list(sys.modules):
        if name == "config" or name == "services" or name.startswith("app."):
            sys.modules.pop(name, None)
    import services
    return importlib.reload(services)


def test_pending_id_rejects_path_traversal(tmp_path):
    services = load_services(tmp_path)
    with pytest.raises(ValueError):
        services.pending_filename("pending__../secret.pdf")


def test_pending_document_gets_finora_suggestion(tmp_path):
    services = load_services(tmp_path)
    source = services.INBOX_DIR / "scan.pdf"
    source.write_bytes(b"%PDF-1.4\n% test placeholder")
    (services.OCR_DIR / "scan.pdf.txt").write_text(
        "Rechnung an Paletten-Service-Schlemeier\nRechnungsnummer RG-2026-100\nGesamtbetrag 119,00 EUR",
        encoding="utf-8",
    )
    items = services.pending_documents()
    assert len(items) == 1
    assert items[0]["status"] == "Pruefen"
    assert items[0]["entity"] == "PSS"
    assert items[0]["finora_suggestion"]["invoice_number"] == "RG-2026-100"


def test_decision_archives_and_teaches_finora(tmp_path):
    services = load_services(tmp_path)
    from models import Decision

    source = services.INBOX_DIR / "scan.pdf"
    source.write_bytes(b"%PDF-1.4\n% test placeholder")
    (services.OCR_DIR / "scan.pdf.txt").write_text(
        "Rechnung an Paletten-Service-Schlemeier\nRechnungsnummer RG-2026-100\nGesamtbetrag 119,00 EUR",
        encoding="utf-8",
    )
    result = services.archive_pending(
        services.pending_id("scan.pdf"),
        Decision(
            document_type="Eingangsrechnung",
            correspondent="Test GmbH",
            entity="PSS",
            document_date="2026-10-06",
            invoice_number="RG-2026-100",
            gross_amount="119,00",
            title="Testrechnung",
        ),
    )
    assert result["status"] == "Abgelegt"
    assert result["target_path"] == "PSS/Buchhaltung/Eingangsrechnungen/2026/Test-GmbH"
    assert not source.exists()
    archived = services.ARCHIVE_DIR / result["target_path"] / result["stored_filename"]
    assert archived.exists()

    con = sqlite3.connect(services.DB_PATH)
    try:
        assert con.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1
        assert con.execute("SELECT COUNT(*) FROM learning_documents").fetchone()[0] == 1
    finally:
        con.close()
