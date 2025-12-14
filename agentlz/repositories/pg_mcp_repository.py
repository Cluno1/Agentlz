from __future__ import annotations
from typing import Any, Dict, List, Sequence
from sqlalchemy import text
from contextlib import closing
from agentlz.core.database import get_pg_engine, get_pg_conn

_MCP_VEC_DIM = 1536


def _to_vector_literal(vec: Sequence[float]) -> str:
    """将 Python 向量序列化为 pgvector 字面量，例如 "[0.1,0.2]"。"""
    return "[" + ",".join(str(float(x)) for x in vec) + "]"

def _to_bigint_array_literal(ids: Sequence[int]) -> str:
    return "{" + ",".join(str(int(i)) for i in ids) + "}"

def _ensure_pg_schema(conn) -> None:
    """确保 pgvector 扩展、`mcp_agents_vec` 表与向量索引存在。

    - 表字段说明：
      - `embedding`：工具描述语义向量（pgvector，维度=dim）
      - `transport`/`command`：与 `name` 共同唯一标识 MCP
      - `trust_score`：可信度得分（trust score，浮点，默认 0），用于融合排序的质量信号
    """
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cur.execute(
            f"CREATE TABLE IF NOT EXISTS mcp_agents_vec (id BIGINT PRIMARY KEY, name TEXT, transport TEXT, command TEXT, description TEXT, category TEXT, embedding VECTOR({_MCP_VEC_DIM}), trust_score REAL DEFAULT 0);"
        )
        try:
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_mcp_agents_vec_embedding ON mcp_agents_vec USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);"
            )
        except Exception:
            pass
        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_mcp_agents_name_tr_cmd ON mcp_agents_vec (name, transport, command);"
        )
    conn.commit()


def upsert_mcp_agent_vector(agent_id: int, name: str, transport: str, command: str, description: str, category: str, embedding: Sequence[float]) -> None:
    """写入或更新向量表 `mcp_agents_vec`（仅 PostgreSQL）。

    - 不处理 `trust_score`（可信度得分），该值由业务层或离线作业更新
    - 若主键存在则进行 UPSERT，更新 `name/transport/command/description/category/embedding`
    """
    v = _to_vector_literal(embedding)
    with closing(get_pg_conn()) as conn:
        _ensure_pg_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO mcp_agents_vec (id, name, transport, command, description, category, embedding) VALUES (%s,%s,%s,%s,%s,%s,%s::vector) ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, transport=EXCLUDED.transport, command=EXCLUDED.command, description=EXCLUDED.description, category=EXCLUDED.category, embedding=%s::vector",
                (agent_id, name, transport, command, description, category, v, v),
            )
        conn.commit()


def search_ids_by_vector(embedding: Sequence[float], k: int = 5) -> List[int]:
    """按语义相似度检索 Top‑k 的 MCP ID 列表（不融合可信度）。"""
    v = _to_vector_literal(embedding)
    ids: List[int] = []
    with closing(get_pg_conn()) as conn:
        _ensure_pg_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM mcp_agents_vec ORDER BY embedding <-> %s::vector LIMIT %s",
                (v, k),
            )
            rows = cur.fetchall()
            ids = [r[0] for r in rows]
    return ids


def search_mcp_hybrid_pg(
    *,
    query_vec: Sequence[float],
    alpha: float = 0.7,
    theta: float = 0.75,
    N: int = 50,
    k: int = 10,
    allowed_ids: Sequence[int] | None = None,
) -> List[Dict[str, Any]]:
    """在 PG 上执行候选限制 + 语义/可信度混合排序。

    当 allowed_ids 非空时，仅在该小集合内进行 Top‑N → 归一化 → 融合排序 → 阈值过滤 → Top‑k。
    """
    """混合排序：语义 Top‑N → 可信度归一化 → 融合打分 → 语义门槛 → Top‑k。

    - 语义分：`sem_score = 1 - (embedding <=> query_vec)`（夹紧到 [0,1]）
    - 可信度：`trust_score` 表示可信度得分（trust score），在候选集内做 min‑max 归一化
    - 融合：`total_score = alpha * sem_score + (1 - alpha) * trust_score_norm`
    - 门槛：`WHERE sem_score >= theta` 保证相关性
    """
    # 使用驱动层原生占位符（psycopg2：%s）以避免在 PostgreSQL 中出现":"语法错误
    base = (
        """
        WITH candidates AS (
          SELECT id, name, transport, command, description, trust_score, embedding
          FROM mcp_agents_vec
          {where_clause}
          ORDER BY embedding <=> %s::vector
          LIMIT %s
        ),
        norm AS (
          SELECT *,
                 COALESCE((trust_score - MIN(COALESCE(trust_score, 0)) OVER ())
                 / NULLIF(MAX(COALESCE(trust_score, 0)) OVER () - MIN(COALESCE(trust_score, 0)) OVER (), 0), 0) AS trust_score_norm,
                 GREATEST(0, 1 - (embedding <=> %s::vector)) AS sem_score
          FROM candidates
        )
        , ranked AS (
          SELECT *, %s * sem_score + (1 - %s) * trust_score_norm AS total_score
          FROM norm
        )
        SELECT id, name, transport, command, description, trust_score, sem_score, total_score
        FROM ranked
        WHERE sem_score >= %s
        ORDER BY total_score DESC
        LIMIT %s
        """
    )
    engine = get_pg_engine()
    with engine.connect() as conn:
        # 使用 exec_driver_sql 走底层驱动，以确保 %s 占位符按顺序绑定
        v = _to_vector_literal(query_vec)
        if allowed_ids and len(allowed_ids) > 0:
            arr = _to_bigint_array_literal(allowed_ids)
            sql = base.format(where_clause="WHERE id = ANY(%s::bigint[])")
            args = (arr, v, int(N), v, float(alpha), float(alpha), float(theta), int(k))
        else:
            sql = base.format(where_clause="")
            args = (v, int(N), v, float(alpha), float(alpha), float(theta), int(k))
        rows = conn.exec_driver_sql(sql, args).mappings().all()
    return [dict(r) for r in rows]


def update_trust_score_pg(agent_id: int, trust_score: float) -> None:
    engine = get_pg_engine()
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE mcp_agents_vec SET trust_score=:s WHERE id=:id"),
            {"id": int(agent_id), "s": float(trust_score)},
        )

def delete_mcp_agent_vector(agent_id: int) -> None:
    engine = get_pg_engine()
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM mcp_agents_vec WHERE id=:id"),
            {"id": int(agent_id)},
        )
