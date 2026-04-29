from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator

from app.core.config import settings


def _sqlite_path() -> Path:
    url = settings.database_url
    prefix = "sqlite:///"
    if url.startswith("sqlite+aiosqlite:///"):
        return Path(url.removeprefix("sqlite+aiosqlite:///"))
    if url.startswith(prefix):
        return Path(url.removeprefix(prefix))
    return Path("./data/rag.db")


DB_PATH = _sqlite_path()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                content_type TEXT,
                file_path TEXT NOT NULL,
                status TEXT NOT NULL,
                error TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ingestion_jobs (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                status TEXT NOT NULL,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(document_id) REFERENCES documents(id)
            );

            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                content TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                page_number INTEGER,
                source_name TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(document_id) REFERENCES documents(id)
            );

            CREATE TABLE IF NOT EXISTS query_logs (
                id TEXT PRIMARY KEY,
                conversation_id TEXT,
                project_id TEXT,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                citations_json TEXT NOT NULL DEFAULT '[]',
                document_ids_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                document_ids_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        _ensure_column(conn, "query_logs", "conversation_id", "TEXT")
        _ensure_column(conn, "query_logs", "project_id", "TEXT")
        _ensure_column(
            conn,
            "query_logs",
            "document_ids_json",
            "TEXT NOT NULL DEFAULT '[]'",
        )
        conn.execute(
            """
            UPDATE query_logs
            SET conversation_id = id
            WHERE conversation_id IS NULL OR conversation_id = ''
            """
        )


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def _chunk_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    chunk = dict(row)
    chunk["metadata"] = json.loads(chunk.get("metadata_json") or "{}")
    return chunk


def _ensure_column(
    conn: sqlite3.Connection, table_name: str, column_name: str, definition: str
) -> None:
    columns = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def create_document(
    *,
    document_id: str,
    filename: str,
    content_type: str | None,
    file_path: str,
    metadata: dict[str, Any],
) -> None:
    now = utc_now()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO documents (
                id, filename, content_type, file_path, status, error,
                metadata_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                filename,
                content_type,
                file_path,
                "created",
                None,
                json.dumps(metadata, ensure_ascii=False),
                now,
                now,
            ),
        )


def update_document_status(
    document_id: str, status: str, error: str | None = None
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE documents
            SET status = ?, error = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, error, utc_now(), document_id),
        )


def get_document(document_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT d.*, COUNT(c.id) AS chunk_count
            FROM documents d
            LEFT JOIN chunks c ON c.document_id = d.id
            WHERE d.id = ?
            GROUP BY d.id
            """,
            (document_id,),
        ).fetchone()
    return _row_to_dict(row)


def list_documents(page: int, page_size: int, status: str | None = None) -> dict[str, Any]:
    offset = (page - 1) * page_size
    params: list[Any] = []
    where = ""
    if status:
        where = "WHERE status = ?"
        params.append(status)

    with get_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) AS count FROM documents {where}", params
        ).fetchone()["count"]
        rows = conn.execute(
            f"""
            SELECT d.*, COUNT(c.id) AS chunk_count
            FROM documents d
            LEFT JOIN chunks c ON c.document_id = d.id
            {where}
            GROUP BY d.id
            ORDER BY d.created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        ).fetchall()
    return {"items": [dict(row) for row in rows], "total": total}


def delete_document(document_id: str) -> bool:
    with get_conn() as conn:
        document = conn.execute(
            "SELECT id FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
        if document is None:
            return False
        conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
        conn.execute("DELETE FROM ingestion_jobs WHERE document_id = ?", (document_id,))
        conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        rows = conn.execute("SELECT * FROM projects").fetchall()
        for row in rows:
            document_ids = json.loads(row["document_ids_json"] or "[]")
            if document_id not in document_ids:
                continue
            next_document_ids = [
                item for item in document_ids if item != document_id
            ]
            conn.execute(
                """
                UPDATE projects
                SET document_ids_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    json.dumps(next_document_ids, ensure_ascii=False),
                    utc_now(),
                    row["id"],
                ),
            )
    return True


def create_project(*, project_id: str, name: str, document_ids: list[str]) -> None:
    now = utc_now()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO projects (
                id, name, document_ids_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                project_id,
                name,
                json.dumps(_unique_ids(document_ids), ensure_ascii=False),
                now,
                now,
            ),
        )


def list_projects() -> dict[str, Any]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM projects
            ORDER BY updated_at DESC, created_at DESC
            """
        ).fetchall()
    items = [_project_row_to_dict(row) for row in rows]
    return {"items": items, "total": len(items)}


def get_project(project_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
    if row is None:
        return None
    return _project_row_to_dict(row)


def delete_project(project_id: str) -> bool:
    with get_conn() as conn:
        cursor = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    return cursor.rowcount > 0


def _project_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["document_ids"] = json.loads(item.pop("document_ids_json") or "[]")
    item["document_count"] = len(item["document_ids"])
    return item


def _unique_ids(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def create_job(job_id: str, document_id: str, status: str = "created") -> None:
    now = utc_now()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO ingestion_jobs (
                id, document_id, status, error, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job_id, document_id, status, None, now, now),
        )


def update_job(job_id: str, status: str, error: str | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE ingestion_jobs
            SET status = ?, error = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, error, utc_now(), job_id),
        )


def get_job(job_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM ingestion_jobs WHERE id = ?", (job_id,)
        ).fetchone()
    return _row_to_dict(row)


def replace_chunks(document_id: str, chunks: list[dict[str, Any]]) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
        conn.executemany(
            """
            INSERT INTO chunks (
                id, document_id, content, chunk_index, page_number,
                source_name, metadata_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    chunk["id"],
                    document_id,
                    chunk["content"],
                    chunk["chunk_index"],
                    chunk.get("page_number"),
                    chunk["source_name"],
                    json.dumps(chunk.get("metadata", {}), ensure_ascii=False),
                    utc_now(),
                )
                for chunk in chunks
            ],
        )


def get_chunks_by_ids(chunk_ids: list[str]) -> list[dict[str, Any]]:
    if not chunk_ids:
        return []
    placeholders = ",".join("?" for _ in chunk_ids)
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM chunks WHERE id IN ({placeholders})", chunk_ids
        ).fetchall()
    by_id = {row["id"]: _chunk_row_to_dict(row) for row in rows}
    return [by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in by_id]


def get_neighbor_chunks(chunk_refs: list[tuple[str, int]], window: int) -> list[dict[str, Any]]:
    if not chunk_refs or window <= 0:
        return []

    seen: set[tuple[str, int]] = set()
    expanded_refs: list[tuple[str, int]] = []
    for document_id, chunk_index in chunk_refs:
        for index in range(chunk_index - window, chunk_index + window + 1):
            if index < 0:
                continue
            key = (document_id, index)
            if key in seen:
                continue
            seen.add(key)
            expanded_refs.append(key)

    clauses = " OR ".join("(document_id = ? AND chunk_index = ?)" for _ in expanded_refs)
    params: list[Any] = []
    for document_id, chunk_index in expanded_refs:
        params.extend([document_id, chunk_index])

    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM chunks
            WHERE {clauses}
            ORDER BY document_id, chunk_index
            """,
            params,
        ).fetchall()
    return [_chunk_row_to_dict(row) for row in rows]


def save_query_log(
    *,
    query_id: str,
    conversation_id: str,
    project_id: str | None,
    question: str,
    answer: str,
    citations: list[dict[str, Any]],
    document_ids: list[str],
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO query_logs (
                id, conversation_id, project_id, question, answer, citations_json,
                document_ids_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                query_id,
                conversation_id,
                project_id,
                question,
                answer,
                json.dumps(citations, ensure_ascii=False),
                json.dumps(document_ids, ensure_ascii=False),
                utc_now(),
            ),
        )


def list_query_logs(page: int, page_size: int) -> dict[str, Any]:
    offset = (page - 1) * page_size
    with get_conn() as conn:
        total = conn.execute(
            "SELECT COUNT(DISTINCT conversation_id) AS count FROM query_logs"
        ).fetchone()["count"]
        rows = conn.execute(
            """
            SELECT q.*
            FROM query_logs q
            JOIN (
                SELECT conversation_id, MAX(created_at) AS latest_at
                FROM query_logs
                GROUP BY conversation_id
            ) latest
              ON latest.conversation_id = q.conversation_id
             AND latest.latest_at = q.created_at
            ORDER BY q.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (page_size, offset),
        ).fetchall()

    items = []
    for row in rows:
        item = dict(row)
        item["citations"] = json.loads(item.pop("citations_json") or "[]")
        item["document_ids"] = json.loads(item.pop("document_ids_json") or "[]")
        items.append(item)
    return {"items": items, "total": total}


def list_query_logs_by_project(project_id: str, limit: int = 30) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT q.*
            FROM query_logs q
            JOIN (
                SELECT conversation_id, MAX(created_at) AS latest_at
                FROM query_logs
                WHERE project_id = ?
                GROUP BY conversation_id
            ) latest
              ON latest.conversation_id = q.conversation_id
             AND latest.latest_at = q.created_at
            WHERE q.project_id = ?
            ORDER BY q.created_at DESC
            LIMIT ?
            """,
            (project_id, project_id, limit),
        ).fetchall()

    items = []
    for row in rows:
        item = dict(row)
        item["citations"] = json.loads(item.pop("citations_json") or "[]")
        item["document_ids"] = json.loads(item.pop("document_ids_json") or "[]")
        items.append(item)
    return items


def list_query_logs_by_conversation(
    conversation_id: str, limit: int = 20
) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM query_logs
            WHERE conversation_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (conversation_id, limit),
        ).fetchall()

    items = []
    for row in reversed(rows):
        item = dict(row)
        item["citations"] = json.loads(item.pop("citations_json") or "[]")
        item["document_ids"] = json.loads(item.pop("document_ids_json") or "[]")
        items.append(item)
    return items


def delete_query_log(query_id: str) -> bool:
    with get_conn() as conn:
        cursor = conn.execute(
            "DELETE FROM query_logs WHERE id = ? OR conversation_id = ?",
            (query_id, query_id),
        )
    return cursor.rowcount > 0
