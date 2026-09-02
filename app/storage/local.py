import hashlib
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings


class LocalStorage:
    def __init__(self) -> None:
        self.upload_dir = Path(settings.upload_dir)
        self.result_dir = Path(settings.result_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.result_dir.mkdir(parents=True, exist_ok=True)

    async def save_upload(
        self, file: UploadFile, document_id: uuid.UUID
    ) -> tuple[str, int, str]:
        suffix = Path(file.filename or "document.pdf").suffix.lower() or ".pdf"
        destination = self.upload_dir / f"{document_id}{suffix}"
        digest = hashlib.sha256()
        size = 0
        with destination.open("wb") as target:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                digest.update(chunk)
                target.write(chunk)
        await file.seek(0)
        return str(destination), size, digest.hexdigest()

    def delete(self, path: str) -> None:
        Path(path).unlink(missing_ok=True)

    def save_result(self, document_id: uuid.UUID, text: str) -> str:
        destination = self.result_dir / f"{document_id}.txt"
        destination.write_text(text, encoding="utf-8")
        return str(destination)


storage = LocalStorage()
