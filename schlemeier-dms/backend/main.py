from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from config import DB_PATH, FINORA_ROOT, FRONTEND_DIR
from models import Decision, DocumentSummary
from services import all_documents, archive_pending, pending_documents, resolve_file

app = FastAPI(title="Schlemeier DMS", version="0.1.0")
app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR)), name="assets")


@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "finora_root": str(FINORA_ROOT),
        "database_exists": DB_PATH.exists(),
        "pending_count": len(pending_documents()),
    }


@app.get("/api/documents", response_model=list[DocumentSummary])
def list_documents(
    status: str | None = Query(None),
    entity: str | None = Query(None),
    q: str = Query(""),
):
    qn = q.casefold().strip()
    items = all_documents()
    if status:
        items = [item for item in items if item["status"] == status]
    if entity:
        items = [item for item in items if item["entity"] == entity]
    if qn:
        items = [
            item for item in items
            if qn in " ".join(
                str(item.get(key, ""))
                for key in ("original_filename", "title", "document_type", "correspondent", "invoice_number")
            ).casefold()
        ]
    return items


@app.get("/api/documents/{document_id}", response_model=DocumentSummary)
def get_document(document_id: str):
    for item in all_documents():
        if item["id"] == document_id:
            return item
    raise HTTPException(status_code=404, detail="Dokument nicht gefunden")


@app.get("/api/documents/{document_id}/file")
def document_file(document_id: str):
    try:
        path = resolve_file(document_id)
    except (ValueError, FileNotFoundError):
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    return FileResponse(path)


@app.post("/api/documents/{document_id}/decision")
def decide_document(document_id: str, decision: Decision):
    if not document_id.startswith("pending__"):
        raise HTTPException(
            status_code=409,
            detail="Bereits abgelegte Dokumente werden in dieser Stufe nicht verschoben.",
        )
    try:
        return archive_pending(document_id, decision)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Offener Beleg wurde nicht gefunden")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/kontoabgleich")
def kontoabgleich():
    return RedirectResponse("http://127.0.0.1:8020/bank")
