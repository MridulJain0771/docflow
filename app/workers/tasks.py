import asyncio
import uuid

from pypdf import PdfReader
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models.document import DocumentJob, DocumentStatus
from app.storage.local import LocalStorage
from app.workers.celery_app import celery_app


async def _set_retry_state(document_id: uuid.UUID, message: str) -> None:
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            job = await session.get(DocumentJob, document_id)
            if job is not None:
                job.status = DocumentStatus.retrying
                job.error_message = message[:2000]
                await session.commit()
    finally:
        await engine.dispose()


async def _set_failed(document_id: uuid.UUID, message: str) -> None:
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            job = await session.get(DocumentJob, document_id)
            if job is not None:
                job.status = DocumentStatus.failed
                job.error_message = message[:2000]
                await session.commit()
    finally:
        await engine.dispose()


async def _process_document(document_id: uuid.UUID) -> None:
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    storage = LocalStorage()
    try:
        async with session_factory() as session:
            job = await session.get(DocumentJob, document_id)
            if job is None:
                raise RuntimeError(f"Document job {document_id} not found")
            job.status = DocumentStatus.processing
            job.progress = 5
            job.error_message = None
            await session.commit()
            stored_path = job.stored_path

            reader = PdfReader(stored_path)
            page_count = len(reader.pages)
            chunks: list[str] = []
            last_progress = 5
            for index, page in enumerate(reader.pages, start=1):
                chunks.append(page.extract_text() or "")
                progress = min(90, 5 + int((index / max(page_count, 1)) * 85))
                if progress >= last_progress + 10 or index == page_count:
                    job.progress = progress
                    await session.commit()
                    last_progress = progress

            text = "\n\n".join(chunks)
            result_path = storage.save_result(document_id, text)
            job.status = DocumentStatus.completed
            job.progress = 100
            job.page_count = page_count
            job.char_count = len(text)
            job.result_path = result_path
            job.error_message = None
            await session.commit()
    finally:
        await engine.dispose()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
def process_document(self, document_id: str) -> None:
    parsed_id = uuid.UUID(document_id)
    try:
        asyncio.run(_process_document(parsed_id))
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            asyncio.run(_set_failed(parsed_id, str(exc)))
            raise
        asyncio.run(_set_retry_state(parsed_id, str(exc)))
        raise self.retry(exc=exc) from exc
