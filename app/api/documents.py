from __future__ import annotations

import json

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from app.db.database import (
    delete_document,
    get_document,
    get_job,
    list_documents,
)
from app.db.schemas import (
    DeleteResponse,
    DocumentDetail,
    DocumentListResponse,
    DocumentUploadResponse,
    JobDetail,
)
from app.ingest.pipeline import ingest_upload, remove_file_quietly
from app.rag.vector_store import get_vector_store


router = APIRouter(tags=["documents"])


def _document_detail(row: dict) -> DocumentDetail:
    metadata = json.loads(row.get("metadata_json") or "{}")
    return DocumentDetail(
        id=row["id"],
        filename=row["filename"],
        content_type=row["content_type"],
        status=row["status"],
        error=row["error"],
        chunk_count=row["chunk_count"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        file_path=row["file_path"],
        metadata=metadata,
    )


@router.post("/documents", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    metadata: str | None = Form(default=None),
) -> DocumentUploadResponse:
    result = await ingest_upload(file, metadata)
    return DocumentUploadResponse(**result)


@router.get("/documents", response_model=DocumentListResponse)
def documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = None,
) -> DocumentListResponse:
    result = list_documents(page=page, page_size=page_size, status=status)
    return DocumentListResponse(**result)


@router.get("/documents/{document_id}", response_model=DocumentDetail)
def document_detail(document_id: str) -> DocumentDetail:
    row = get_document(document_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return _document_detail(row)


@router.delete("/documents/{document_id}", response_model=DeleteResponse)
async def remove_document(document_id: str) -> DeleteResponse:
    row = get_document(document_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")

    await get_vector_store().delete_document(document_id)
    deleted = delete_document(document_id)
    remove_file_quietly(row["file_path"])
    return DeleteResponse(deleted=deleted)


@router.get("/jobs/{job_id}", response_model=JobDetail)
def job_detail(job_id: str) -> JobDetail:
    row = get_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobDetail(**row)

