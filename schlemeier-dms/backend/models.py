from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Entity = Literal["PSS", "BP", "PSSpandau", "Privat", "Unklar"]
PrivatePerson = Literal["Yasmin", "Frank", "Marina", "Karl", "Unklar", ""]
DocumentStatus = Literal["Neu", "Pruefen", "Zugeordnet", "Abgelegt", "Duplikat"]


class Decision(BaseModel):
    document_type: str
    correspondent: str = "Unklar"
    entity: Entity
    private_person: PrivatePerson = ""
    document_date: str = ""
    invoice_number: str = ""
    gross_amount: str = ""
    title: str = "Dokument"


class DocumentSummary(BaseModel):
    id: str
    original_filename: str
    title: str
    document_type: str
    entity: str
    private_person: str = ""
    correspondent: str = "Unklar"
    document_date: str = ""
    invoice_number: str = ""
    gross_amount: str = ""
    status: DocumentStatus
    confidence: float = Field(ge=0, le=1)
    target_path: str = ""
    source: str = "Finora"
    file_url: str
    is_pdf: bool
    finora_suggestion: dict | None = None
