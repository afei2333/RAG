from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings


class QdrantVectorStore:
    def __init__(self, base_url: str, collection: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.collection = collection

    async def ensure_collection(self, vector_size: int) -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/collections/{self.collection}"
                )
            except httpx.ConnectError as exc:
                raise RuntimeError(
                    "Cannot connect to Qdrant. Start the Qdrant service and check "
                    f"QDRANT_URL={self.base_url}."
                ) from exc
            if response.status_code == 200:
                return
            if response.status_code != 404:
                response.raise_for_status()
            create_response = await client.put(
                f"{self.base_url}/collections/{self.collection}",
                json={
                    "vectors": {
                        "size": vector_size,
                        "distance": "Cosine",
                    }
                },
            )
            create_response.raise_for_status()

    async def upsert_chunks(
        self,
        *,
        document_id: str,
        chunks: list[dict[str, Any]],
        vectors: list[list[float]],
    ) -> None:
        if not vectors:
            return
        await self.ensure_collection(vector_size=len(vectors[0]))
        points = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            metadata = chunk.get("metadata", {})
            points.append(
                {
                    "id": chunk["id"],
                    "vector": vector,
                    "payload": {
                        "document_id": document_id,
                        "chunk_id": chunk["id"],
                        "source_name": chunk["source_name"],
                        "page_number": chunk.get("page_number"),
                        "content_type": metadata.get("content_type", "body"),
                    },
                }
            )

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.put(
                f"{self.base_url}/collections/{self.collection}/points",
                json={"points": points},
            )
            response.raise_for_status()

    async def search(
        self,
        vector: list[float],
        top_k: int,
        score_threshold: float,
        document_id: str | None = None,
        document_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "vector": vector,
            "limit": top_k,
            "score_threshold": score_threshold,
            "with_payload": True,
        }
        if document_ids is not None:
            payload["filter"] = {
                "must": [
                    {
                        "key": "document_id",
                        "match": {"any": document_ids},
                    }
                ]
            }
        elif document_id:
            payload["filter"] = {
                "must": [
                    {
                        "key": "document_id",
                        "match": {"value": document_id},
                    }
                ]
            }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/collections/{self.collection}/points/search",
                json=payload,
            )
            response.raise_for_status()
        return response.json().get("result", [])

    async def delete_document(self, document_id: str) -> None:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/collections/{self.collection}/points/delete",
                json={
                    "filter": {
                        "must": [
                            {
                                "key": "document_id",
                                "match": {"value": document_id},
                            }
                        ]
                    }
                },
            )
            if response.status_code != 404:
                response.raise_for_status()


def get_vector_store() -> QdrantVectorStore:
    return QdrantVectorStore(
        base_url=settings.qdrant_url,
        collection=settings.qdrant_collection,
    )
