from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence
from contextlib import closing

from agentlz.core.database import get_pg_conn


def _to_vector_literal(vec: Sequence[float]) -> str:
    return "[" + ",".join(str(float(x)) for x in vec) + "]"


def _parse_vector_text(s: str) -> List[float]:
    t = s.strip()
    if t.startswith("[") and t.endswith("]"):
        t = t[1:-1]
    if not t:
        return []
    return [float(x) for x in t.split(",") if x]


def _set_tenant(cur, tenant_id: str) -> None:
    cur.execute("SET LOCAL app.current_tenant = %s", (tenant_id,))


def create_chunk_embedding(*, tenant_id: str, chunk_id: str, doc_id: str, embedding: Sequence[float], content: Optional[str] = None) -> Dict[str, Any]:
    v = _to_vector_literal(embedding)
    with closing(get_pg_conn()) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            _set_tenant(cur, tenant_id)
            cur.execute(
                "INSERT INTO chunk_embeddings (chunk_id, tenant_id, doc_id, embedding, content) VALUES (%s,%s,%s,%s::vector,%s) ON CONFLICT (chunk_id) DO NOTHING",
                (chunk_id, tenant_id, doc_id, v, content),
            )
            cur.execute(
                "SELECT chunk_id, tenant_id, doc_id, content, created_at FROM chunk_embeddings WHERE chunk_id=%s",
                (chunk_id,),
            )
            row = cur.fetchone()
        conn.commit()
    if not row:
        return {}
    return {
        "chunk_id": row[0],
        "tenant_id": row[1],
        "doc_id": row[2],
        "content": row[3],
        "created_at": row[4],
    }


def get_chunk_embedding(*, tenant_id: str, chunk_id: str, include_vector: bool = False) -> Optional[Dict[str, Any]]:
    with closing(get_pg_conn()) as conn:
        with conn.cursor() as cur:
            _set_tenant(cur, tenant_id)
            if include_vector:
                cur.execute(
                    "SELECT chunk_id, tenant_id, doc_id, content, created_at, embedding::text FROM chunk_embeddings WHERE chunk_id=%s",
                    (chunk_id,),
                )
            else:
                cur.execute(
                    "SELECT chunk_id, tenant_id, doc_id, content, created_at FROM chunk_embeddings WHERE chunk_id=%s",
                    (chunk_id,),
                )
            row = cur.fetchone()
    if not row:
        return None
    if include_vector:
        return {
            "chunk_id": row[0],
            "tenant_id": row[1],
            "doc_id": row[2],
            "content": row[3],
            "created_at": row[4],
            "embedding": _parse_vector_text(row[5] or ""),
        }
    return {
        "chunk_id": row[0],
        "tenant_id": row[1],
        "doc_id": row[2],
        "content": row[3],
        "created_at": row[4],
    }


def list_chunk_embeddings(*, tenant_id: str, doc_id: Optional[str] = None, limit: int = 20, offset: int = 0, include_vector: bool = False) -> List[Dict[str, Any]]:
    with closing(get_pg_conn()) as conn:
        with conn.cursor() as cur:
            _set_tenant(cur, tenant_id)
            if include_vector:
                if doc_id:
                    cur.execute(
                        "SELECT chunk_id, tenant_id, doc_id, content, created_at, embedding::text FROM chunk_embeddings WHERE doc_id=%s ORDER BY created_at DESC LIMIT %s OFFSET %s",
                        (doc_id, limit, offset),
                    )
                else:
                    cur.execute(
                        "SELECT chunk_id, tenant_id, doc_id, content, created_at, embedding::text FROM chunk_embeddings ORDER BY created_at DESC LIMIT %s OFFSET %s",
                        (limit, offset),
                    )
                rows = cur.fetchall()
                return [
                    {
                        "chunk_id": r[0],
                        "tenant_id": r[1],
                        "doc_id": r[2],
                        "content": r[3],
                        "created_at": r[4],
                        "embedding": _parse_vector_text(r[5] or ""),
                    }
                    for r in rows
                ]
            else:
                if doc_id:
                    cur.execute(
                        "SELECT chunk_id, tenant_id, doc_id, content, created_at FROM chunk_embeddings WHERE doc_id=%s ORDER BY created_at DESC LIMIT %s OFFSET %s",
                        (doc_id, limit, offset),
                    )
                else:
                    cur.execute(
                        "SELECT chunk_id, tenant_id, doc_id, content, created_at FROM chunk_embeddings ORDER BY created_at DESC LIMIT %s OFFSET %s",
                        (limit, offset),
                    )
                rows = cur.fetchall()
                return [
                    {
                        "chunk_id": r[0],
                        "tenant_id": r[1],
                        "doc_id": r[2],
                        "content": r[3],
                        "created_at": r[4],
                    }
                    for r in rows
                ]


def update_chunk_embedding(*, tenant_id: str, chunk_id: str, embedding: Optional[Sequence[float]] = None, content: Optional[str] = None) -> Optional[Dict[str, Any]]:
    sets: List[str] = []
    params: List[Any] = []
    if embedding is not None:
        sets.append("embedding=%s::vector")
        params.append(_to_vector_literal(embedding))
    if content is not None:
        sets.append("content=%s")
        params.append(content)
    with closing(get_pg_conn()) as conn:
        with conn.cursor() as cur:
            _set_tenant(cur, tenant_id)
            if sets:
                sql = "UPDATE chunk_embeddings SET " + ", ".join(sets) + " WHERE chunk_id=%s"
                cur.execute(sql, (*params, chunk_id))
            cur.execute(
                "SELECT chunk_id, tenant_id, doc_id, content, created_at FROM chunk_embeddings WHERE chunk_id=%s",
                (chunk_id,),
            )
            row = cur.fetchone()
        conn.commit()
    if not row:
        return None
    return {
        "chunk_id": row[0],
        "tenant_id": row[1],
        "doc_id": row[2],
        "content": row[3],
        "created_at": row[4],
    }


def delete_chunk_embedding(*, tenant_id: str, chunk_id: str) -> bool:
    with closing(get_pg_conn()) as conn:
        with conn.cursor() as cur:
            _set_tenant(cur, tenant_id)
            cur.execute("DELETE FROM chunk_embeddings WHERE chunk_id=%s", (chunk_id,))
            deleted = cur.rowcount > 0
        conn.commit()
    return deleted