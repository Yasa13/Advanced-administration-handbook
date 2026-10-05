from __future__ import annotations

from pathlib import Path
import shutil
import uuid

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .batch import create_batch, delete_batch, get_batch_item
from .bank import bank_overview, import_bank_file
from .classifier import classify, build_target_folder
from .config import ARCHIVE_DIR, FINORA_ROOT, INBOX_DIR, OCR_DIR, PROCESSED_ORIGINALS_DIR, ensure_directories
from .db import confirm_payment_match, init_db, log_document, record_learning, remove_payment_match
from .ocr import extract_text

BASE_DIR = Path(__file__).resolve().parent.parent
ensure_directories()

app = FastAPI(title="Finora Dokument-Assistent")
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))
init_db()

ALLOWED_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png"}


def _safe_component(value: str, fallback: str = "Dokument") -> str:
    replacements = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"})
    value = value.translate(replacements)
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in value)
    safe = "-".join(part for part in safe.split("-") if part)
    return safe.strip("-_") or fallback


def _ocr_sidecar(temp_name: str) -> Path:
    return OCR_DIR / f"{temp_name}.txt"


def _prepare_upload(file: UploadFile) -> dict[str, str]:
    suffix = Path(file.filename or "upload.bin").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError(f"{file.filename or 'Datei'}: Nur PDF/JPG/PNG erlaubt.")

    original_name = file.filename or f"upload{suffix}"
    temp_name = f"{uuid.uuid4().hex}{suffix}"
    temp_path = INBOX_DIR / temp_name
    with temp_path.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)

    text = extract_text(temp_path)
    _ocr_sidecar(temp_name).write_text(text, encoding="utf-8", errors="ignore")
    return {"temp_name": temp_name, "original_name": original_name}


def _render_review(
    request: Request,
    temp_name: str,
    original_name: str,
    *,
    batch_id: str = "",
    batch_index: int = 0,
    batch_total: int = 1,
):
    source = INBOX_DIR / temp_name
    if not source.exists():
        return RedirectResponse(url="/?error=missing", status_code=303)

    sidecar = _ocr_sidecar(temp_name)
    if sidecar.exists():
        text = sidecar.read_text(encoding="utf-8", errors="ignore")
    else:
        text = extract_text(source)
        sidecar.write_text(text, encoding="utf-8", errors="ignore")

    result = classify(text, original_name)
    return templates.TemplateResponse(
        "review.html",
        {
            "request": request,
            "temp_name": temp_name,
            "original_name": original_name,
            "ocr_text": text,
            "r": result,
            "storage_root": str(FINORA_ROOT),
            "archive_root": str(ARCHIVE_DIR),
            "batch_id": batch_id,
            "batch_index": batch_index,
            "batch_total": batch_total,
        },
    )


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request, "storage_root": str(FINORA_ROOT)})




@app.get("/bank", response_class=HTMLResponse)
def bank_page(request: Request):
    raw_search_tx = request.query_params.get("search_tx", "")
    try:
        search_tx = int(raw_search_tx) if raw_search_tx else None
    except ValueError:
        search_tx = None
    search_query = request.query_params.get("q", "")
    return templates.TemplateResponse(
        "bank.html",
        {
            "request": request,
            "transactions": bank_overview(search_tx_id=search_tx, search_query=search_query),
            "storage_root": str(FINORA_ROOT),
        },
    )


@app.post("/bank/import")
async def bank_import(file: UploadFile = File(...)):
    filename = file.filename or "bankdatei"
    allowed = (".csv", ".xml", ".camt", ".sta", ".mt940", ".txt")
    if not filename.lower().endswith(allowed):
        return RedirectResponse(url="/bank?error=format", status_code=303)
    try:
        raw = await file.read()
        result = import_bank_file(raw, filename)
    except Exception as exc:
        from urllib.parse import quote
        return RedirectResponse(url=f"/bank?error=import&message={quote(str(exc))}", status_code=303)
    return RedirectResponse(
        url=(f"/bank?imported={result['inserted']}&duplicates={result['duplicates']}"
             f"&format={result.get('source_format','')}"),
        status_code=303,
    )


@app.post("/bank/confirm")
def bank_confirm(
    transaction_id: int = Form(...),
    document_id: int = Form(...),
    match_amount: float = Form(...),
    confidence: float = Form(0.0),
):
    try:
        result = confirm_payment_match(transaction_id, document_id, match_amount, confidence)
    except Exception:
        return RedirectResponse(url="/bank?error=match", status_code=303)
    return RedirectResponse(
        url=(f"/bank?matched=1&status={result['status']}"
             f"&tx_status={result['transaction_status']}"),
        status_code=303,
    )


@app.post("/bank/unmatch")
def bank_unmatch(match_id: int = Form(...)):
    try:
        remove_payment_match(match_id)
    except Exception:
        return RedirectResponse(url="/bank?error=unmatch", status_code=303)
    return RedirectResponse(url="/bank?unmatched=1", status_code=303)


@app.post("/upload", response_class=HTMLResponse)
async def upload(request: Request, files: list[UploadFile] = File(...)):
    if not files:
        return templates.TemplateResponse(
            "upload.html",
            {"request": request, "error": "Bitte mindestens eine Datei auswählen.", "storage_root": str(FINORA_ROOT)},
            status_code=400,
        )

    items: list[dict[str, str]] = []
    errors: list[str] = []
    for file in files:
        try:
            items.append(_prepare_upload(file))
        except ValueError as exc:
            errors.append(str(exc))
        except Exception as exc:  # Keep the batch usable if one OCR/import fails.
            errors.append(f"{file.filename or 'Datei'} konnte nicht verarbeitet werden: {exc}")

    if not items:
        return templates.TemplateResponse(
            "upload.html",
            {"request": request, "error": "Keine Datei konnte verarbeitet werden. " + " ".join(errors), "storage_root": str(FINORA_ROOT)},
            status_code=400,
        )

    if len(items) == 1:
        return _render_review(request, items[0]["temp_name"], items[0]["original_name"])

    batch_id = create_batch(items)
    url = f"/batch/{batch_id}/0"
    if errors:
        url += "?warnings=1"
    return RedirectResponse(url=url, status_code=303)


@app.get("/batch/{batch_id}/{index}", response_class=HTMLResponse)
def review_batch(request: Request, batch_id: str, index: int):
    item, total = get_batch_item(batch_id, index)
    if not item:
        return RedirectResponse(url="/?error=batch", status_code=303)
    return _render_review(
        request,
        item["temp_name"],
        item["original_name"],
        batch_id=batch_id,
        batch_index=index,
        batch_total=total,
    )


@app.post("/confirm")
def confirm(
    temp_name: str = Form(...),
    original_name: str = Form(...),
    document_type: str = Form(...),
    correspondent: str = Form(...),
    addressee_type: str = Form(...),
    addressee_name: str = Form(""),
    private_person: str = Form(""),
    document_date: str = Form(""),
    invoice_number: str = Form(""),
    gross_amount: str = Form(""),
    title: str = Form(...),
    target_folder: str = Form(""),
    predicted_document_type: str = Form(""),
    predicted_correspondent: str = Form(""),
    predicted_addressee_type: str = Form(""),
    predicted_private_person: str = Form(""),
    confidence_document_type: float = Form(0.0),
    confidence_correspondent: float = Form(0.0),
    confidence_addressee: float = Form(0.0),
    batch_id: str = Form(""),
    batch_index: int = Form(0),
    batch_total: int = Form(1),
):
    source = INBOX_DIR / temp_name
    if not source.exists():
        return RedirectResponse(url="/?error=missing", status_code=303)

    target_folder = (
        target_folder.strip().replace("\\", "/").lstrip("/")
        or build_target_folder(document_type, document_date, correspondent, addressee_type, private_person)
    )
    target_path = Path(target_folder)
    if target_path.is_absolute() or ".." in target_path.parts:
        target_folder = build_target_folder(document_type, document_date, correspondent, addressee_type, private_person)

    final_dir = ARCHIVE_DIR / target_folder
    final_dir.mkdir(parents=True, exist_ok=True)

    safe_title = _safe_component(title, source.stem)
    final_path = final_dir / f"{safe_title}{source.suffix.lower()}"
    if final_path.exists():
        final_path = final_dir / f"{safe_title}_ID-{uuid.uuid4().hex[:8]}{source.suffix.lower()}"

    original_copy_name = f"{uuid.uuid4().hex[:8]}_{_safe_component(Path(original_name).stem)}{source.suffix.lower()}"
    original_copy_path = PROCESSED_ORIGINALS_DIR / original_copy_name
    shutil.copy2(source, original_copy_path)
    shutil.copy2(source, final_path)

    classification = {
        "document_type": document_type,
        "correspondent": correspondent,
        "addressee_type": addressee_type,
        "addressee_name": addressee_name,
        "private_person": private_person,
        "document_date": document_date,
        "invoice_number": invoice_number,
        "gross_amount": gross_amount,
        "title": title,
        "target_folder": target_folder,
        "confidence_document_type": confidence_document_type,
        "confidence_correspondent": confidence_correspondent,
        "confidence_addressee": confidence_addressee,
    }
    document_id = log_document(
        original_filename=original_name,
        stored_filename=final_path.name,
        original_copy_path=str(original_copy_path),
        file_path=str(final_path),
        classification=classification,
    )

    sidecar = _ocr_sidecar(temp_name)
    ocr_text = sidecar.read_text(encoding="utf-8", errors="ignore") if sidecar.exists() else ""
    record_learning(
        document_id=document_id,
        ocr_text=ocr_text,
        confirmed={
            "document_type": document_type,
            "correspondent": correspondent,
            "addressee_type": addressee_type,
            "private_person": private_person,
        },
        predicted={
            "document_type": predicted_document_type,
            "correspondent": predicted_correspondent,
            "addressee_type": predicted_addressee_type,
            "private_person": predicted_private_person,
        },
        confidences={
            "document_type": confidence_document_type,
            "correspondent": confidence_correspondent,
            "addressee_type": confidence_addressee,
            "private_person": confidence_addressee,
        },
    )

    source.unlink(missing_ok=True)
    sidecar.unlink(missing_ok=True)

    if batch_id and batch_total > 1:
        next_index = batch_index + 1
        if next_index < batch_total:
            return RedirectResponse(url=f"/batch/{batch_id}/{next_index}?saved=1", status_code=303)
        delete_batch(batch_id)
        return RedirectResponse(url=f"/?batch_saved={batch_total}", status_code=303)

    return RedirectResponse(url=f"/?saved=1&path={final_path}", status_code=303)
