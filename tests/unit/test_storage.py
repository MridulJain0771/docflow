import hashlib
import uuid

import pytest
from fastapi import UploadFile

from app.storage.local import LocalStorage


def test_result_file_uses_document_id(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.storage.local.settings.result_dir", str(tmp_path))
    storage = LocalStorage()
    document_id = uuid.uuid4()

    path = storage.save_result(document_id, "hello")

    assert path.endswith(f"{document_id}.txt")
    assert tmp_path.joinpath(f"{document_id}.txt").read_text() == "hello"


@pytest.mark.asyncio
async def test_upload_calculates_sha256(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.storage.local.settings.upload_dir", str(tmp_path))
    storage = LocalStorage()
    payload = b"pdf-like-content"
    upload = UploadFile(filename="sample.pdf", file=__import__("io").BytesIO(payload))

    path, size, digest = await storage.save_upload(upload, uuid.uuid4())

    assert size == len(payload)
    assert digest == hashlib.sha256(payload).hexdigest()
    assert __import__("pathlib").Path(path).read_bytes() == payload
