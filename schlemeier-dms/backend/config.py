from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FINORA_DIR = REPO_ROOT / "finora"
FRONTEND_DIR = REPO_ROOT / "schlemeier-dms" / "frontend"

if str(FINORA_DIR) not in sys.path:
    sys.path.insert(0, str(FINORA_DIR))

from app.config import (  # noqa: E402
    ARCHIVE_DIR,
    BATCH_DIR,
    DB_PATH,
    FINORA_ROOT,
    INBOX_DIR,
    OCR_DIR,
    PROCESSED_ORIGINALS_DIR,
    ensure_directories,
)

ensure_directories()
