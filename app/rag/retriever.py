from __future__ import annotations

from app.core.config import settings
from app.db.database import get_chunks_by_ids, get_neighbor_chunks
from app.rag.embeddings import get_embedding_provider
from app.rag.vector_store import get_vector_store


async def retrieve(
    question: str,
    top_k: int,
    score_threshold: float,
    document_id: str | None = None,
    document_ids: list[str] | None = None,
) -> list[dict]:
    if document_ids is not None and not document_ids:
        return []

    embedding_provider = get_embedding_provider()
    vector_store = get_vector_store()
    query_vector = (await embedding_provider.embed_texts([question]))[0]
    candidate_k = max(top_k * 3, top_k + settings.context_window_chunks * 2)
    hits = await vector_store.search(
        vector=query_vector,
        top_k=candidate_k,
        score_threshold=score_threshold,
        document_id=document_id,
        document_ids=document_ids,
    )
    chunk_ids = [hit["payload"]["chunk_id"] for hit in hits]
    chunks = get_chunks_by_ids(chunk_ids)
    score_by_chunk_id = {
        hit["payload"]["chunk_id"]: float(hit["score"]) for hit in hits
    }

    ranked_results = []
    for chunk in chunks:
        chunk_id = chunk["id"]
        chunk["score"] = score_by_chunk_id.get(chunk_id, 0.0)
        ranked_results.append(chunk)

    seed_chunks = ranked_results[:top_k]
    if settings.context_window_chunks <= 0:
        return seed_chunks

    neighbor_refs = [
        (chunk["document_id"], int(chunk["chunk_index"])) for chunk in seed_chunks
    ]
    neighbors = get_neighbor_chunks(neighbor_refs, settings.context_window_chunks)
    score_by_ref = {
        (chunk["document_id"], int(chunk["chunk_index"])): chunk["score"]
        for chunk in seed_chunks
    }
    seed_ids = {chunk["id"] for chunk in seed_chunks}

    expanded_results = []
    for chunk in neighbors:
        ref = (chunk["document_id"], int(chunk["chunk_index"]))
        chunk["score"] = score_by_ref.get(ref, 0.0)
        chunk["retrieval_role"] = "hit" if chunk["id"] in seed_ids else "neighbor"
        expanded_results.append(chunk)

    if not expanded_results:
        return seed_chunks
    return expanded_results
