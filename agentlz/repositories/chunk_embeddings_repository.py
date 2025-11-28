from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Literal
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


def search_similar_chunks(
    *,
    tenant_id: str,
    embedding: Sequence[float],
    doc_id: Optional[str] = None,
    doc_ids: Optional[Sequence[str]] = None,
    distance_metric: Literal["euclidean", "cosine"] = "euclidean",
    limit: int = 10,
    include_vector: bool = False
) -> List[Dict[str, Any]]:
    """向量相似度搜索
    
    基于给定的embedding向量，使用指定的距离度量方式搜索最相似的文本块。
    
    参数:
        - tenant_id: 租户标识，用于RLS隔离
        - embedding: 查询向量，维度需与存储向量一致(1536维)
        - doc_id: 可选的文档ID过滤条件，为空则搜索所有文档
        - distance_metric: 距离度量方式，可选"euclidean"或"cosine"
        - limit: 返回结果数量上限
        - include_vector: 是否返回向量字段
    
    返回值:
        - 相似文本块列表，按相似度升序排列（距离越小越相似）
        - 每个结果包含: chunk_id, doc_id, content, created_at, similarity_score
        - 当include_vector=True时额外包含embedding向量
    
    异常:
        - ValueError: 当distance_metric不是"euclidean"或"cosine"时
        - RuntimeError: 当向量维度不匹配或数据库查询失败时
    """
    if distance_metric not in ["euclidean", "cosine"]:
        raise ValueError(f"不支持的度量方式: {distance_metric}，请选择 'euclidean' 或 'cosine'")
    
    # 验证向量维度
    if len(embedding) != 1536:
        raise ValueError(f"向量维度不匹配: 期望1536维，实际{len(embedding)}维")
    
    # 将向量转换为pgvector格式
    vector_literal = _to_vector_literal(embedding)
    
    with closing(get_pg_conn()) as conn:
        with conn.cursor() as cur:
            # 设置租户上下文
            cur.execute("SET LOCAL app.current_tenant = %s", (tenant_id,))
            
            # 构建查询SQL
            if distance_metric == "euclidean":
                # 欧几里得距离: 使用内置的<->操作符
                distance_expr = "embedding <-> %s::vector"
            else:
                # 余弦相似度: 使用<=>操作符 (1 - cosine_similarity)
                distance_expr = "embedding <=> %s::vector"
            
            # 构建WHERE条件
            where_conditions = []
            params = [vector_literal]
            
            if doc_ids is not None:
                if len(doc_ids) == 0:
                    return []
                where_conditions.append("doc_id = ANY(%s)")
                params.append(list(doc_ids))
            elif doc_id:
                where_conditions.append("doc_id = %s")
                params.append(doc_id)
            
            where_clause = ""
            if where_conditions:
                where_clause = "WHERE " + " AND ".join(where_conditions)
            
            # 选择字段
            if include_vector:
                select_fields = "chunk_id, tenant_id, doc_id, content, created_at, embedding::text, "
            else:
                select_fields = "chunk_id, tenant_id, doc_id, content, created_at, "
            
            # 完整的SQL查询 - 按距离升序排列（距离越小越相似）
            sql = f"""
                SELECT {select_fields} {distance_expr} as distance
                FROM chunk_embeddings
                {where_clause}
                ORDER BY distance
                LIMIT %s
            """
            
            params.append(limit)
            
            try:
                cur.execute(sql, params)
                rows = cur.fetchall()
            except Exception as e:
                raise RuntimeError(f"向量搜索查询失败: {str(e)}")
            
            results = []
            for row in rows:
                if include_vector:
                    result = {
                        "chunk_id": row[0],
                        "tenant_id": row[1],
                        "doc_id": row[2], 
                        "content": row[3],
                        "created_at": row[4],
                        "embedding": _parse_vector_text(row[5] or ""),
                        "similarity_score": float(row[6]),
                    }
                else:
                    result = {
                        "chunk_id": row[0],
                        "tenant_id": row[1],
                        "doc_id": row[2],
                        "content": row[3], 
                        "created_at": row[4],
                        "similarity_score": float(row[5]),
                    }
                results.append(result)
            
            return results