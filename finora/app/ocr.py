from pathlib import Path

from PIL import Image
from pypdf import PdfReader
import pytesseract


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        text_parts: list[str] = []
        try:
            reader = PdfReader(str(path))
            for page in reader.pages:
                text_parts.append(page.extract_text() or "")
        except Exception:
            text_parts = []
        text = "\n".join(text_parts).strip()
        if text:
            return text
        return (
            "PDF enthaelt keinen direkt extrahierbaren Text. "
            "Gescannte PDFs werden in einer spaeteren Version mit OCRmyPDF verarbeitet."
        )

    if suffix in {".jpg", ".jpeg", ".png"}:
        try:
            image = Image.open(path)
            return pytesseract.image_to_string(image, lang="deu+eng")
        except pytesseract.TesseractNotFoundError:
            return (
                "OCR FEHLER: Tesseract wurde auf diesem PC nicht gefunden. "
                "Installiere Tesseract OCR und starte Finora danach neu."
            )

    raise ValueError("Nicht unterstuetztes Dateiformat")
