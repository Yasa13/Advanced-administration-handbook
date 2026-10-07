from __future__ import annotations

import json
import re
import shutil
import sqlite3
import uuid
from pathlib import Path

from config import (
    ARCHIVE_DIR,
    BATCH_DIR,
    DB_PATH,
    FINORA_ROOT,
    INBOX_DIR,
    OCR_DIR,
    PROCESSED_ORIGINALS_DIR,
)
from models import Decision

from app.classifier import build_target_folder, classify
from app.db import init_db, log_document, record_learning
from app.ocr import extract_text

ALLOWED_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png"}
ENTITY_LABELS = {
    "PSS": "Paletten-Service Schlemeier",
    "BP": "Berliner Paletten",
    "PSSpandau": "Paletten-Service Spandau",
    "Privat": "Privat",
    "Unklar": "Unklar",
}

init_db()


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def safe_component(value: str, fallback: str = "Dokument") -> str:
    translations = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"})
    value = (value or fallback).translate(translations)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-_")
    return safe or fallback


def pending_id(filename: str) -> str:
    return f"pending__{filename}"


def pending_filename(document_id: str) -> str:
    if not document_id.startswith("pending__"):
        raise ValueError("Not a pending document id")
    filename = document_id.removeprefix("pending__")
    if not filename or Path(filename).name != filename:
        raise ValueError("Invalid pending document id")
    return filename


def recover_original_name(temp_name: str) -> str:
    for manifest in BATCH_DIR.glob("*.json"):
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for item in payload.get("items", []):
            if item.get("temp_name") == temp_name and item.get("original_name"):
                return str(item["original_name"])
    return temp_name


def ocr_text(path: Path) -> str:
    sidecar = OCR_DIR / f"{path.name}.txt"
    if sidecar.exists():
        return sidecar.read_text(encoding="utf-8", errors="ignore")
    text = extract_text(path)
    sidecar.write_text(text, encoding="utf-8", errors="ignore")
    return text


def confidence(*values: float) -> float:
    return max(0.0, min(1.0, max((float(v or 0) for v in values), default=0.0)))


def pending_documents() -> list[dict]:
    result: list[dict] = []
    if not INBOX_DIR.exists():
        return result
    for path in sorted(INBOX_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not path.is_file() or path.suffix.lower() not in ALLOWED_SUFFIXES:
            continue
        original_name = recover_original_name(path.name)
        suggestion = classify(ocr_text(path), original_name)
        suggestion_data = {
            "document_type": suggestion.document_type,
            "entity": suggestion.addressee_type,
            "private_person": suggestion.private_person or "",
            "correspondent": suggestion.correspondent,
            "document_date": suggestion.document_date,
            "invoice_number": suggestion.invoice_number,
            "gross_amount": suggestion.gross_amount,
            "title": suggestion.title,
            "target_path": suggestion.target_folder,
            "learning_note": suggestion.learning_note,
            "learned_from_history": suggestion.learned_from_history,
        }
        result.append({
            "id": pending_id(path.name),
            "original_filename": original_name,
            "title": suggestion.title or Path(original_name).stem,
            "document_type": suggestion.document_type,
            "entity": suggestion.addressee_type,
            "private_person": suggestion.private_person or "",
            "correspondent": suggestion.correspondent,
            "document_date": suggestion.document_date,
            "invoice_number": suggestion.invoice_number,
            "gross_amount": suggestion.gross_amount,
            "status": "Pruefen",
            "confidence": confidence(suggestion.confidence_document_type, suggestion.confidence_correspondent, suggestion.confidence_addressee),
            "target_path": suggestion.target_folder,
            "source": "Finora-Inbox",
            "file_url": f"/api/documents/{pending_id(path.name)}/file",
            "is_pdf": path.suffix.lower() == ".pdf",
            "finora_suggestion": suggestion_data,
        })
    return result


def archived_documents() -> list[dict]:
    if not DB_PATH.exists():
        return []
    con = connect()
    try:
        rows = con.execute("""
            SELECT d.id, d.original_filename, d.stored_filename, d.file_path,
                   c.document_type, c.correspondent, c.addressee_type, c.private_person,
                   c.document_date, c.invoice_number, c.gross_amount, c.title, c.target_folder,
                   c.confidence_document_type, c.confidence_correspondent, c.confidence_addressee
            FROM documents d
            LEFT JOIN classifications c ON c.id = (
                SELECT c2.id FROM classifications c2
                WHERE c2.document_id = d.id ORDER BY c2.id DESC LIMIT 1
            )
            ORDER BY d.id DESC
        """).fetchall()
        result: list[dict] = []
        for row in rows:
            item = dict(row)
            file_path = Path(item.get("file_path") or "")
            result.append({
                "id": str(item["id"]),
                "original_filename": item.get("original_filename") or item.get("stored_filename") or "Dokument",
                "title": item.get("title") or Path(item.get("original_filename") or "Dokument").stem,
                "document_type": item.get("document_type") or "Sonstiges",
                "entity": item.get("addressee_type") or "Unklar",
                "private_person": item.get("private_person") or "",
                "correspondent": item.get("correspondent") or "Unklar",
                "document_date": item.get("document_date") or "",
                "invoice_number": item.get("invoice_number") or "",
                "gross_amount": item.get("gross_amount") or "",
                "status": "Abgelegt",
                "confidence": confidence(item.get("confidence_document_type") or 0, item.get("confidence_correspondent") or 0, item.get("confidence_addressee") or 0),
                "target_path": item.get("target_folder") or "",
                "source": "Finora-Archiv",
                "file_url": f"/api/documents/{item['id']}/file",
                "is_pdf": file_path.suffix.lower() == ".pdf",
                "finora_suggestion": None,
            })
        return result
    finally:
        con.close()


def all_documents() -> list[dict]:
    return pending_documents() + archived_documents()


def resolve_file(document_id: str) -> Path:
    if document_id.startswith("pending__"):
        path = INBOX_DIR / pending_filename(document_id)
    else:
        numeric_id = int(document_id)
        con = connect()
        try:
            row = con.execute("SELECT file_path FROM documents WHERE id=?", (numeric_id,)).fetchone()
        finally:
            con.close()
        if not row or not row["file_path"]:
            raise FileNotFoundError(document_id)
        path = Path(row["file_path"])
    path.resolve().relative_to(FINORA_ROOT.resolve())
    if not path.is_file():
        raise FileNotFoundError(document_id)
    return path


def archive_pending(document_id: str, decision: Decision) -> dict:
    filename = pending_filename(document_id)
    source = INBOX_DIR / filename
    if not source.is_file():
        raise FileNotFoundError(document_id)

    original_name = recover_original_name(filename)
    text = ocr_text(source)
    predicted = classify(text, original_name)
    private_person = decision.private_person if decision.entity == "Privat" else ""
    target_folder = build_target_folder(
        decision.document_type,
        decision.document_date,
        decision.correspondent,
        decision.entity,
        private_person,
    )
    target_rel = Path(target_folder)
    if target_rel.is_absolute() or ".." in target_rel.parts:
        raise ValueError("Invalid target path")

    final_dir = ARCHIVE_DIR / target_rel
    final_dir.mkdir(parents=True, exist_ok=True)
    safe_title = safe_component(decision.title, source.stem)
    final_path = final_dir / f"{safe_title}{source.suffix.lower()}"
    if final_path.exists():
        final_path = final_dir / f"{safe_title}_ID-{uuid.uuid4().hex[:8]}{source.suffix.lower()}"

    original_copy_path = PROCESSED_ORIGINALS_DIR / f"{uuid.uuid4().hex[:8]}_{safe_component(Path(original_name).stem)}{source.suffix.lower()}"
    shutil.copy2(source, original_copy_path)
    shutil.copy2(source, final_path)

    classification = {
        "document_type": decision.document_type,
        "correspondent": decision.correspondent,
        "addressee_type": decision.entity,
        "addressee_name": ENTITY_LABELS.get(decision.entity, decision.entity),
        "private_person": private_person,
        "document_date": decision.document_date,
        "invoice_number": decision.invoice_number,
        "gross_amount": decision.gross_amount,
        "title": decision.title,
        "target_folder": target_folder,
        "confidence_document_type": predicted.confidence_document_type,
        "confidence_correspondent": predicted.confidence_correspondent,
        "confidence_addressee": predicted.confidence_addressee,
    }
    document_db_id = log_document(
        original_name,
        final_path.name,
        str(original_copy_path),
        str(final_path),
        classification,
    )
    record_learning(
        document_id=document_db_id,
        ocr_text=text,
        confirmed={
            "document_type": decision.document_type,
            "correspondent": decision.correspondent,
            "addressee_type": decision.entity,
            "private_person": private_person,
        },
        predicted={
            "document_type": predicted.document_type,
            "correspondent": predicted.correspondent,
            "addressee_type": predicted.addressee_type,
            "private_person": predicted.private_person,
        },
        confidences={
            "document_type": predicted.confidence_document_type,
            "correspondent": predicted.confidence_correspondent,
            "addressee_type": predicted.confidence_addressee,
            "private_person": predicted.confidence_addressee,
        },
    )
    source.unlink(missing_ok=True)
    (OCR_DIR / f"{filename}.txt").unlink(missing_ok=True)
    return {
        "document_id": str(document_db_id),
        "status": "Abgelegt",
        "target_path": target_folder,
        "stored_filename": final_path.name,
    }
