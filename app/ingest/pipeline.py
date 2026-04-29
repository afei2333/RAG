from __future__ import annotations

import json
import logging
from pathlib import Path
import shutil
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import settings
from app.db.database import (
    create_document,
    create_job,
    replace_chunks,
    update_document_status,
    update_job,
)
from app.ingest.figures import extract_pdf_figures
from app.ingest.loaders import load_document
from app.ingest.splitter import split_pages
from app.rag.embeddings import get_embedding_provider
from app.rag.vector_store import get_vector_store

logger = logging.getLogger(__name__)


def parse_metadata(raw_metadata: str | None) -> dict:
    if not raw_metadata:
        return {}
    try:
        parsed = json.loads(raw_metadata)
    except json.JSONDecodeError as exc:
        raise ValueError("metadata must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("metadata must be a JSON object")
    return parsed


async def save_upload(file: UploadFile, document_id: str) -> Path:
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    original_name = Path(file.filename or "document").name
    stored_name = f"{document_id}_{original_name}"
    target_path = settings.storage_dir / stored_name

    with target_path.open("wb") as output:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
    await file.close()
    return target_path


async def ingest_upload(file: UploadFile, raw_metadata: str | None = None) -> dict:
    metadata = parse_metadata(raw_metadata)
    document_id = f"doc_{uuid4().hex}"
    job_id = f"job_{uuid4().hex}"
    file_path = await save_upload(file, document_id)

    create_document(
        document_id=document_id,
        filename=file.filename or file_path.name,
        content_type=file.content_type,
        file_path=str(file_path),
        metadata=metadata,
    )
    create_job(job_id, document_id)

    try:
        update_document_status(document_id, "processing")
        update_job(job_id, "processing")
        pages = load_document(file_path)
        chunks = split_pages(
            pages,
            source_name=file.filename or file_path.name,
            document_id=document_id,
        )
        chunks.extend(
            extract_pdf_figures(
                file_path,
                pages=pages,
                source_name=file.filename or file_path.name,
                document_id=document_id,
                start_index=len(chunks),
            )
        )
        if not chunks:
            raise ValueError("No text content found in document")

        replace_chunks(document_id, chunks)
        embedding_provider = get_embedding_provider()
        vectors = await embedding_provider.embed_texts([chunk["content"] for chunk in chunks])
        vector_store = get_vector_store()
        await vector_store.upsert_chunks(
            document_id=document_id,
            chunks=chunks,
            vectors=vectors,
        )

        update_document_status(document_id, "completed")
        update_job(job_id, "completed")
        return {"document_id": document_id, "job_id": job_id, "status": "completed"}
    except Exception as exc:
        logger.exception("Document ingestion failed")
        error = str(exc)
        update_document_status(document_id, "failed", error)
        update_job(job_id, "failed", error)
        return {
            "document_id": document_id,
            "job_id": job_id,
            "status": "failed",
            "error": error,
        }


def remove_file_quietly(file_path: str) -> None:
    path = Path(file_path)
    if path.exists():
        path.unlink()


def remove_document_assets(document_id: str) -> None:
    path = settings.storage_dir / document_id
    if path.exists():
        shutil.rmtree(path)


def reset_storage() -> None:
    if settings.storage_dir.exists():
        shutil.rmtree(settings.storage_dir)
