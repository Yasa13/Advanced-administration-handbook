from __future__ import annotations

import os
from pathlib import Path


def _default_root() -> Path:
    if os.name == "nt":
        return Path(r"C:\Finora")
    return Path.home() / "Finora"


FINORA_ROOT = Path(os.environ.get("FINORA_ROOT", str(_default_root()))).expanduser()
INBOX_DIR = FINORA_ROOT / "Eingang"
PROCESSED_ORIGINALS_DIR = INBOX_DIR / "Verarbeitet" / "Originale"
ARCHIVE_DIR = FINORA_ROOT / "Ablage"
DATABASE_DIR = FINORA_ROOT / "Datenbank"
OCR_DIR = FINORA_ROOT / "OCR"
BATCH_DIR = OCR_DIR / "Batches"
BACKUP_DIR = FINORA_ROOT / "Backup"
DB_PATH = DATABASE_DIR / "finora.db"


def ensure_directories() -> None:
    for folder in (
        FINORA_ROOT,
        INBOX_DIR,
        PROCESSED_ORIGINALS_DIR,
        ARCHIVE_DIR,
        DATABASE_DIR,
        OCR_DIR,
        BATCH_DIR,
        BACKUP_DIR,
    ):
        folder.mkdir(parents=True, exist_ok=True)
