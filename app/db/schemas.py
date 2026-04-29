from typing import Any

from pydantic import BaseModel, Field


class DocumentSummary(BaseModel):
    id: str
    filename: str
    content_type: str | None = None
    status: str
    error: str | None = None
    chunk_count: int = 0
    created_at: str
    updated_at: str


class DocumentListResponse(BaseModel):
    items: list[DocumentSummary]
    total: int


class DocumentUploadResponse(BaseModel):
    document_id: str
    job_id: str
    status: str
    error: str | None = None


class DocumentDetail(DocumentSummary):
    file_path: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobDetail(BaseModel):
    id: str
    document_id: str
    status: str
    error: str | None = None
    created_at: str
    updated_at: str


class DeleteResponse(BaseModel):
    deleted: bool


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    document_ids: list[str] = Field(min_length=1)


class ProjectSummary(BaseModel):
    id: str
    name: str
    document_ids: list[str] = Field(default_factory=list)
    document_count: int = 0
    created_at: str
    updated_at: str


class ProjectListResponse(BaseModel):
    items: list[ProjectSummary]
    total: int


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    conversation_id: str | None = None
    document_id: str | None = None
    document_ids: list[str] | None = None
    project_id: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)
    score_threshold: float | None = Field(default=None, ge=0)


class Citation(BaseModel):
    document_id: str
    chunk_id: str
    source_name: str
    page_number: int | None = None
    score: float
    retrieval_role: str | None = None
    content_type: str | None = None
    image_url: str | None = None
    caption: str | None = None
    text: str


class QueryResponse(BaseModel):
    query_id: str | None = None
    conversation_id: str | None = None
    answer: str
    citations: list[Citation]


class QueryLogSummary(BaseModel):
    id: str
    conversation_id: str | None = None
    project_id: str | None = None
    question: str
    answer: str
    citations: list[Citation]
    document_ids: list[str] = Field(default_factory=list)
    created_at: str


class QueryLogListResponse(BaseModel):
    items: list[QueryLogSummary]
    total: int
