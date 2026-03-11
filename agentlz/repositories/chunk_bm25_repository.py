from __future__ import annotations

from typing import Any, Dict, List, Sequence, Optional
from contextlib import closing

from agentlz.core.database import get_pg_conn


def _set_tenant(cur, tenant_id: str) -> None:
    cur.execute("SET LOCAL app.current_tenant = %s", (tenant_id,))


def insert_chunk_bm25(*, tenant_id: str, chunk_id: str, doc_id: str, content: str, content_seg: str) -> None:
    """
    插入或覆盖 BM25 文本分块
    说明：
    - 依赖 chunk_embeddings 的外键约束，保持 chunk_id 一致性
    - RLS 通过 app.current_tenant 控制访问隔离
    """
    with closing(get_pg_conn()) as conn:
        with conn.cursor() as cur:
            _set_tenant(cur, tenant_id)
            cur.execute(
                """
                INSERT INTO chunk_bm25 (chunk_id, tenant_id, doc_id, content, content_seg)
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT (chunk_id) DO UPDATE SET content = EXCLUDED.content, content_seg = EXCLUDED.content_seg, doc_id = EXCLUDED.doc_id
                """,
                (chunk_id, tenant_id, doc_id, content, content_seg),
            )
        conn.commit()


def list_chunks_by_doc_ids(*, tenant_id: str, doc_ids: Sequence[str]) -> List[Dict[str, Any]]:
    """
    按文档ID集返回 BM25 文本分块
    返回字段：chunk_id, doc_id, content
    """
    ids = [str(x or "").strip() for x in (doc_ids or [])]
    ids = [x for x in ids if x]
    if not ids:
        return []
    with closing(get_pg_conn()) as conn:
        with conn.cursor() as cur:
            _set_tenant(cur, tenant_id)
            cur.execute(
                """
                SELECT chunk_id, doc_id, content
                FROM chunk_bm25
                WHERE doc_id = ANY(%s)
                """,
                (ids,),
            )
            rows = cur.fetchall()
    return [
        {
            "chunk_id": r[0],
            "doc_id": r[1],
            "content": r[2],
        }
        for r in rows or []
    ]


def search_chunks_by_tsquery(
    *,
    tenant_id: str,
    doc_ids: Sequence[str],
    tsquery: str,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    使用中文全文检索（zhparser + zh_cn 配置）按照 tsquery 检索分块
    
    参数:
    - tenant_id: 租户标识
    - doc_ids: 文档ID列表（过滤范围）
    - tsquery: tsquery 查询字符串（例如: '配置 & Agent & MCP'）
    - limit: 返回条数上限
    
    返回:
    - 列表: {chunk_id, doc_id, content, score}
    """
    ids = [str(x or "").strip() for x in (doc_ids or [])]
    ids = [x for x in ids if x]
    if not ids or not isinstance(tsquery, str) or tsquery.strip() == "":
        return []
    with closing(get_pg_conn()) as conn:
        with conn.cursor() as cur:
            _set_tenant(cur, tenant_id)
            cur.execute(
                """
                SELECT chunk_id, doc_id, content,
                       ts_rank(content_seg_fts, to_tsquery('simple', %s)) AS score
                FROM chunk_bm25
                WHERE doc_id = ANY(%s)
                  AND content_seg_fts @@ to_tsquery('simple', %s)
                ORDER BY score DESC
                LIMIT %s
                """,
                (tsquery, list(ids), tsquery, int(limit)),
            )
            rows = cur.fetchall()
    return [
        {
            "chunk_id": r[0],
            "doc_id": r[1],
            "content": r[2],
            "score": float(r[3] or 0.0),
        }
        for r in rows or []
    ]
