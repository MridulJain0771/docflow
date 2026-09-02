import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.models.document import DocumentStatus
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.services.documents import create_document_job, get_document_job, list_document_jobs
from app.storage.local import storage
from app.workers.tasks import process_document

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> DocumentResponse:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="Only PDF uploads are supported")

    document_id = uuid.uuid4()
    stored_path, size_bytes, sha256 = await storage.save_upload(file, document_id)
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if size_bytes > max_bytes:
        storage.delete(stored_path)
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {settings.max_upload_mb} MB upload limit",
        )

    job, created = await create_document_job(
        session,
        document_id=document_id,
        original_filename=file.filename or "document.pdf",
        stored_path=stored_path,
        sha256=sha256,
        content_type=file.content_type,
        size_bytes=size_bytes,
    )
    if created:
        process_document.delay(str(job.id))
    else:
        storage.delete(stored_path)
    return DocumentResponse.model_validate(job)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> DocumentResponse:
    job = await get_document_job(session, document_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse.model_validate(job)


@router.get("/{document_id}/result", response_class=FileResponse)
async def download_result(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    job = await get_document_job(session, document_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if job.status != DocumentStatus.completed or not job.result_path:
        raise HTTPException(status_code=409, detail="Document result is not ready")
    return FileResponse(
        job.result_path,
        media_type="text/plain; charset=utf-8",
        filename=f"{document_id}.txt",
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> DocumentListResponse:
    jobs, total = await list_document_jobs(session, limit=limit, offset=offset)
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(job) for job in jobs],
        total=total,
    )
