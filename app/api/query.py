from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.db.database import (
    delete_query_log,
    get_project,
    list_query_logs,
    list_query_logs_by_project,
    list_query_logs_by_conversation,
    save_query_log,
)
from app.db.schemas import (
    Citation,
    DeleteResponse,
    QueryLogListResponse,
    QueryRequest,
    QueryResponse,
)
from app.rag.generator import get_llm_provider
from app.rag.prompts import build_messages
from app.rag.retriever import retrieve


router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query_knowledge_base(request: QueryRequest) -> QueryResponse:
    prepared = await _prepare_query(request)
    conversation_id = prepared["conversation_id"]
    limited_contexts = prepared["contexts"]

    if not limited_contexts:
        answer = "未在当前知识库中找到足够相关的资料。"
        citations: list[dict] = []
    else:
        messages = build_messages(
            request.question,
            limited_contexts,
            conversation_history=prepared["conversation_history"],
        )
        answer = await get_llm_provider().generate(messages)
        citations = [_citation_from_chunk(chunk) for chunk in limited_contexts]
        answer = _append_inline_figures(answer, citations)

    query_id = f"query_{uuid4().hex}"
    save_query_log(
        query_id=query_id,
        conversation_id=conversation_id,
        project_id=request.project_id,
        question=request.question,
        answer=answer,
        citations=citations,
        document_ids=_cited_document_ids(request, citations, prepared["document_ids"]),
    )
    return QueryResponse(
        query_id=query_id,
        conversation_id=conversation_id,
        answer=answer,
        citations=[Citation(**citation) for citation in citations],
    )


@router.post("/query/stream")
async def stream_query_knowledge_base(request: QueryRequest) -> StreamingResponse:
    return StreamingResponse(
        _stream_query_events(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _prepare_query(request: QueryRequest) -> dict:
    top_k = request.top_k or settings.default_top_k
    score_threshold = (
        request.score_threshold
        if request.score_threshold is not None
        else settings.default_score_threshold
    )

    conversation_id = request.conversation_id or f"conv_{uuid4().hex}"
    conversation_history = list_query_logs_by_conversation(conversation_id, limit=6)
    document_ids = _document_ids_for_request(request)
    retrieval_question = "\n".join(
        [
            *(item["question"] for item in conversation_history[-3:]),
            request.question,
        ]
    )

    contexts = await retrieve(
        question=retrieval_question,
        top_k=top_k,
        score_threshold=score_threshold,
        document_id=request.document_id if not document_ids else None,
        document_ids=document_ids,
    )
    return {
        "conversation_id": conversation_id,
        "conversation_history": conversation_history,
        "document_ids": document_ids,
        "contexts": contexts[: settings.max_context_chunks],
    }


async def _stream_query_events(request: QueryRequest) -> AsyncIterator[str]:
    try:
        yield _sse_comment("stream-open")
        prepared = await _prepare_query(request)
        conversation_id = prepared["conversation_id"]
        limited_contexts = prepared["contexts"]
        query_id = f"query_{uuid4().hex}"
        yield _sse("meta", {"query_id": query_id, "conversation_id": conversation_id})

        if not limited_contexts:
            answer = "未在当前知识库中找到足够相关的资料。"
            citations: list[dict] = []
            yield _sse("answer", {"text": answer})
        else:
            citations = [_citation_from_chunk(chunk) for chunk in limited_contexts]
            yield _sse("citations", {"citations": citations})
            messages = build_messages(
                request.question,
                limited_contexts,
                conversation_history=prepared["conversation_history"],
            )
            answer_parts: list[str] = []
            if settings.cloud_llm_stream:
                async for event in get_llm_provider().stream_generate(messages):
                    if event["type"] == "answer":
                        answer_parts.append(event["text"])
                    yield _sse(event["type"], {"text": event["text"]})
                    await asyncio.sleep(0)
                answer = "".join(answer_parts)
            else:
                answer = await get_llm_provider().generate(messages)
                yield _sse("answer", {"text": answer})
            answer_with_figures = _append_inline_figures(answer, citations)
            answer = answer_with_figures
            yield _sse("final_answer", {"text": answer})

        save_query_log(
            query_id=query_id,
            conversation_id=conversation_id,
            project_id=request.project_id,
            question=request.question,
            answer=answer,
            citations=citations,
            document_ids=_cited_document_ids(request, citations, prepared["document_ids"]),
        )
        yield _sse("done", {"query_id": query_id, "conversation_id": conversation_id})
    except Exception as exc:
        yield _sse("error", {"message": str(exc)})


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _sse_comment(value: str) -> str:
    padding = " " * 2048
    return f": {value}{padding}\n\n"


def _cited_document_ids(
    request: QueryRequest,
    citations: list[dict],
    document_ids: list[str] | None,
) -> list[str]:
    cited_document_ids = sorted(
        {
            citation["document_id"]
            for citation in citations
            if citation.get("document_id")
        }
    )
    for document_id in [request.document_id, *(document_ids or [])]:
        if document_id and document_id not in cited_document_ids:
            cited_document_ids.append(document_id)
    return cited_document_ids


def _document_ids_for_request(request: QueryRequest) -> list[str] | None:
    if request.project_id:
        project = get_project(request.project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return project["document_ids"]
    if request.document_ids:
        return request.document_ids
    return None


def _citation_from_chunk(chunk: dict) -> dict:
    metadata = chunk.get("metadata", {})
    content_type = metadata.get("content_type", "body")
    text_limit = 4000 if content_type == "table" else 500
    return {
        "document_id": chunk["document_id"],
        "chunk_id": chunk["id"],
        "source_name": chunk["source_name"],
        "page_number": chunk["page_number"],
        "score": chunk["score"],
        "retrieval_role": chunk.get("retrieval_role", "hit"),
        "content_type": content_type,
        "image_url": metadata.get("image_url") if content_type == "figure" else None,
        "caption": metadata.get("caption") if content_type == "figure" else None,
        "text": chunk["content"][:text_limit],
    }


def _append_inline_figures(answer: str, citations: list[dict]) -> str:
    figures: list[tuple[int, dict]] = []
    seen_urls = set()
    for citation_number, citation in enumerate(citations, start=1):
        image_url = citation.get("image_url")
        if not image_url or image_url in seen_urls:
            continue
        seen_urls.add(image_url)
        figures.append((citation_number, citation))

    if not figures:
        return answer

    lines = answer.rstrip().splitlines()
    inserted_urls: set[str] = set()
    output_lines: list[str] = []
    for line in lines:
        output_lines.append(line)
        matching_figures = [
            figure
            for citation_number, figure in figures
            if re.search(rf"\[{citation_number}\]", line)
            and figure.get("image_url") not in inserted_urls
        ]
        for figure in matching_figures:
            output_lines.extend(["", _figure_markdown(figure)])
            inserted_urls.add(figure["image_url"])

    remaining_figures = [
        figure
        for _, figure in figures
        if figure.get("image_url") not in inserted_urls
    ]
    if not remaining_figures:
        return "\n".join(output_lines).rstrip()

    figure_blocks = ["### 相关图片"]
    for figure in remaining_figures[:3]:
        figure_blocks.append(_figure_markdown(figure))

    return "\n".join(output_lines).rstrip() + "\n\n" + "\n\n".join(figure_blocks)


def _figure_markdown(figure: dict) -> str:
    caption = figure.get("caption") or "相关图片"
    page = f"第 {figure['page_number']} 页" if figure.get("page_number") else ""
    source = figure.get("source_name") or "来源文档"
    description = " · ".join(part for part in [source, page, caption] if part)
    return "\n".join(
        [
            f"![{_escape_markdown_alt(caption)}]({figure['image_url']})",
            f"*{description}*",
        ]
    )


def _escape_markdown_alt(value: str) -> str:
    return value.replace("[", "(").replace("]", ")").replace("\n", " ").strip()


@router.get("/queries", response_model=QueryLogListResponse)
def query_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    project_id: str | None = None,
) -> QueryLogListResponse:
    if project_id:
        items = list_query_logs_by_project(project_id, limit=page_size)
        return QueryLogListResponse(items=items, total=len(items))
    result = list_query_logs(page=page, page_size=page_size)
    return QueryLogListResponse(**result)


@router.get("/queries/{conversation_id}", response_model=QueryLogListResponse)
def query_conversation(conversation_id: str) -> QueryLogListResponse:
    items = list_query_logs_by_conversation(conversation_id, limit=100)
    if not items:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return QueryLogListResponse(items=items, total=len(items))


@router.delete("/queries/{query_id}", response_model=DeleteResponse)
def remove_query_history(query_id: str) -> DeleteResponse:
    deleted = delete_query_log(query_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Query history not found")
    return DeleteResponse(deleted=deleted)
