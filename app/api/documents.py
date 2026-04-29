from __future__ import annotations

import json
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from app.db.database import (
    create_project,
    delete_document,
    delete_project,
    get_document,
    get_job,
    get_project,
    list_documents,
    list_projects,
)
from app.db.schemas import (
    DeleteResponse,
    DocumentDetail,
    DocumentListResponse,
    DocumentUploadResponse,
    JobDetail,
    ProjectCreateRequest,
    ProjectListResponse,
    ProjectSummary,
)
from app.ingest.pipeline import (
    ingest_upload,
    remove_document_assets,
    remove_file_quietly,
)
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
    remove_document_assets(document_id)
    return DeleteResponse(deleted=deleted)


@router.get("/jobs/{job_id}", response_model=JobDetail)
def job_detail(job_id: str) -> JobDetail:
    row = get_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobDetail(**row)


@router.post("/projects", response_model=ProjectSummary)
def create_knowledge_project(request: ProjectCreateRequest) -> ProjectSummary:
    name = request.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Project name is required")
    missing_ids = [
        document_id
        for document_id in request.document_ids
        if get_document(document_id) is None
    ]
    if missing_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Documents not found: {', '.join(missing_ids)}",
        )

    project_id = f"project_{uuid4().hex}"
    create_project(
        project_id=project_id,
        name=name,
        document_ids=request.document_ids,
    )
    project = get_project(project_id)
    return ProjectSummary(**project)


@router.get("/projects", response_model=ProjectListResponse)
def projects() -> ProjectListResponse:
    return ProjectListResponse(**list_projects())


@router.get("/projects/{project_id}", response_model=ProjectSummary)
def project_detail(project_id: str) -> ProjectSummary:
    project = get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectSummary(**project)


@router.delete("/projects/{project_id}", response_model=DeleteResponse)
def remove_project(project_id: str) -> DeleteResponse:
    deleted = delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    return DeleteResponse(deleted=deleted)
