from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from .config import BATCH_DIR


def create_batch(items: list[dict[str, str]]) -> str:
    """Create a local batch manifest and return its ID."""
    batch_id = uuid.uuid4().hex
    payload = {"id": batch_id, "items": items}
    batch_path(batch_id).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return batch_id


def batch_path(batch_id: str) -> Path:
    safe = "".join(c for c in batch_id if c.isalnum() or c in "-_" )
    return BATCH_DIR / f"{safe}.json"


def load_batch(batch_id: str) -> dict[str, Any] | None:
    path = batch_path(batch_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return None
    return data


def get_batch_item(batch_id: str, index: int) -> tuple[dict[str, str] | None, int]:
    data = load_batch(batch_id)
    if not data:
        return None, 0
    items = data["items"]
    total = len(items)
    if index < 0 or index >= total:
        return None, total
    item = items[index]
    if not isinstance(item, dict):
        return None, total
    return item, total


def delete_batch(batch_id: str) -> None:
    batch_path(batch_id).unlink(missing_ok=True)
