from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.db.database import (
    delete_query_log,
    list_query_logs,
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
    top_k = request.top_k or settings.default_top_k
    score_threshold = (
        request.score_threshold
        if request.score_threshold is not None
        else settings.default_score_threshold
    )

    conversation_id = request.conversation_id or f"conv_{uuid4().hex}"
    conversation_history = list_query_logs_by_conversation(conversation_id, limit=6)
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
        document_id=request.document_id,
    )
    limited_contexts = contexts[: settings.max_context_chunks]

    if not limited_contexts:
        answer = "未在当前知识库中找到足够相关的资料。"
        citations: list[dict] = []
    else:
        messages = build_messages(
            request.question,
            limited_contexts,
            conversation_history=conversation_history,
        )
        answer = await get_llm_provider().generate(messages)
        citations = [_citation_from_chunk(chunk) for chunk in limited_contexts]
        answer = _append_inline_figures(answer, citations)

    query_id = f"query_{uuid4().hex}"
    document_ids = sorted(
        {
            citation["document_id"]
            for citation in citations
            if citation.get("document_id")
        }
    )
    if request.document_id and request.document_id not in document_ids:
        document_ids.append(request.document_id)

    save_query_log(
        query_id=query_id,
        conversation_id=conversation_id,
        question=request.question,
        answer=answer,
        citations=citations,
        document_ids=document_ids,
    )
    return QueryResponse(
        query_id=query_id,
        conversation_id=conversation_id,
        answer=answer,
        citations=[Citation(**citation) for citation in citations],
    )


def _citation_from_chunk(chunk: dict) -> dict:
    metadata = chunk.get("metadata", {})
    content_type = metadata.get("content_type", "body")
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
        "text": chunk["content"][:500],
    }


def _append_inline_figures(answer: str, citations: list[dict]) -> str:
    figures = []
    seen_urls = set()
    for citation in citations:
        image_url = citation.get("image_url")
        if not image_url or image_url in seen_urls:
            continue
        seen_urls.add(image_url)
        figures.append(citation)

    if not figures:
        return answer

    figure_blocks = ["### 相关图片"]
    for index, figure in enumerate(figures[:3], start=1):
        caption = figure.get("caption") or f"相关图片 {index}"
        page = f"第 {figure['page_number']} 页" if figure.get("page_number") else ""
        source = figure.get("source_name") or "来源文档"
        description = " · ".join(part for part in [source, page, caption] if part)
        figure_blocks.append(
            "\n".join(
                [
                    f"![{_escape_markdown_alt(caption)}]({figure['image_url']})",
                    f"*{description}*",
                ]
            )
        )

    return f"{answer.rstrip()}\n\n" + "\n\n".join(figure_blocks)


def _escape_markdown_alt(value: str) -> str:
    return value.replace("[", "(").replace("]", ")").replace("\n", " ").strip()


@router.get("/queries", response_model=QueryLogListResponse)
def query_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> QueryLogListResponse:
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
