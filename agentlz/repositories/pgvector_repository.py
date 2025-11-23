from __future__ import annotations

import os
from typing import List, Sequence
from contextlib import closing

from agentlz.core.database import get_pg_conn




def _to_vector_literal(vec: Sequence[float]) -> str:
    """将向量序列化为 pgvector 字面量字符串，如 "[0.1,0.2]"。"""
    return "[" + ",".join(str(float(x)) for x in vec) + "]"


def _ensure_pg_schema(conn, dim: int) -> None:
    """确保 pgvector 扩展与 mcp_agents_vec 表及索引已存在。"""
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cur.execute(
            f"CREATE TABLE IF NOT EXISTS mcp_agents_vec (id BIGINT PRIMARY KEY, name TEXT, description TEXT, category TEXT, embedding VECTOR({dim}));"
        )
        try:
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_mcp_agents_vec_embedding ON mcp_agents_vec USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);"
            )
        except Exception:
            pass
    conn.commit()


def upsert_mcp_agent_vector(agent_id: int, name: str, description: str, category: str, embedding: Sequence[float]) -> None:
    """写入或更新 MCP Agent 的向量信息，仅操作 PostgreSQL。"""
    dim = len(embedding) if hasattr(embedding, "__len__") else 512
    v = _to_vector_literal(embedding)
    with closing(get_pg_conn()) as conn:
        _ensure_pg_schema(conn, dim)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO mcp_agents_vec (id, name, description, category, embedding) VALUES (%s,%s,%s,%s,%s::vector) ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, description=EXCLUDED.description, category=EXCLUDED.category, embedding=%s::vector",
                (agent_id, name, description, category, v, v),
            )
        conn.commit()


def search_ids_by_vector(embedding: Sequence[float], k: int = 5) -> List[int]:
    """根据查询向量检索相似的 Agent ID 列表（PostgreSQL）。"""
    dim = len(embedding) if hasattr(embedding, "__len__") else 512
    v = _to_vector_literal(embedding)
    ids: List[int] = []
    with closing(get_pg_conn()) as conn:
        _ensure_pg_schema(conn, dim)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM mcp_agents_vec ORDER BY embedding <-> %s::vector LIMIT %s",
                (v, k),
            )
            rows = cur.fetchall()
            ids = [r[0] for r in rows]
    return ids
  