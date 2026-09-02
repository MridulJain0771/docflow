import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentJob, DocumentStatus


async def get_by_checksum(session: AsyncSession, sha256: str) -> DocumentJob | None:
    result = await session.execute(select(DocumentJob).where(DocumentJob.sha256 == sha256))
    return result.scalar_one_or_none()


async def create_document_job(
    session: AsyncSession,
    *,
    document_id: uuid.UUID,
    original_filename: str,
    stored_path: str,
    sha256: str,
    content_type: str,
    size_bytes: int,
) -> tuple[DocumentJob, bool]:
    existing = await get_by_checksum(session, sha256)
    if existing is not None:
        return existing, False

    job = DocumentJob(
        id=document_id,
        original_filename=original_filename,
        stored_path=stored_path,
        sha256=sha256,
        content_type=content_type,
        size_bytes=size_bytes,
        status=DocumentStatus.queued,
        progress=0,
    )
    session.add(job)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = await get_by_checksum(session, sha256)
        if existing is None:
            raise
        return existing, False

    await session.refresh(job)
    return job, True


async def get_document_job(session: AsyncSession, document_id: uuid.UUID) -> DocumentJob | None:
    return await session.get(DocumentJob, document_id)


async def list_document_jobs(
    session: AsyncSession, *, limit: int = 20, offset: int = 0
) -> tuple[list[DocumentJob], int]:
    total = await session.scalar(select(func.count()).select_from(DocumentJob))
    result = await session.execute(
        select(DocumentJob).order_by(DocumentJob.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), int(total or 0)
