from pathlib import Path

from app import batch


def test_create_and_load_batch(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, "BATCH_DIR", tmp_path)
    batch_id = batch.create_batch([
        {"temp_name": "a.pdf", "original_name": "A.pdf"},
        {"temp_name": "b.jpg", "original_name": "B.jpg"},
    ])
    item, total = batch.get_batch_item(batch_id, 0)
    assert total == 2
    assert item == {"temp_name": "a.pdf", "original_name": "A.pdf"}
    assert batch.batch_path(batch_id).exists()


def test_batch_out_of_range_and_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, "BATCH_DIR", tmp_path)
    batch_id = batch.create_batch([{"temp_name": "a.pdf", "original_name": "A.pdf"}])
    item, total = batch.get_batch_item(batch_id, 5)
    assert item is None
    assert total == 1
    batch.delete_batch(batch_id)
    assert not batch.batch_path(batch_id).exists()
