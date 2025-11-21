from typing import Any, Dict, Optional, List

from agentlz.core.embedding_model_factory import get_hf_embeddings
from agentlz.repositories.mcp_repository import (
    create_mcp_agent as _create_mysql_mcp,
    update_mcp_agent as _update_mysql_mcp,
    get_mcp_agents_by_ids as _get_mcp_agents_by_ids,
)
from agentlz.repositories.pgvector_repository import (
    upsert_mcp_agent_vector as _upsert_mcp_vector,
    search_ids_by_vector as _search_ids_by_vector,
)

_EMB = None

def _get_embedder():
    """获取并缓存嵌入模型，用于文本向量化。"""
    global _EMB
    if _EMB is None:
        _EMB = get_hf_embeddings()
    return _EMB


def create_mcp_agent_service(payload: Dict[str, Any]) -> Dict[str, Any]:
    """创建 MCP 代理（MySQL），生成嵌入并同步 PG 向量表。"""
    row = _create_mysql_mcp(payload)
    text = (row.get("description") or "") + " " + (row.get("category") or "")
    vec = _get_embedder().embed_query(text.strip())
    _upsert_mcp_vector(int(row.get("id")), row.get("name") or "", row.get("description") or "", row.get("category") or "", vec)
    return row


def update_mcp_agent_service(agent_id: int, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """更新 MCP 代理（MySQL），若描述/分类变更则重新嵌入并同步 PG。"""
    need_vector_sync = any(k in payload for k in ("description", "category"))
    row = _update_mysql_mcp(agent_id, payload)
    if row and need_vector_sync:
        text = (row.get("description") or "") + " " + (row.get("category") or "")
        vec = _get_embedder().embed_query(text.strip())
        _upsert_mcp_vector(int(row.get("id")), row.get("name") or "", row.get("description") or "", row.get("category") or "", vec)
    return row

def search_mcp_agents_service(query: str, k: int = 5) -> List[Dict[str, Any]]:
    """向量化查询语句，PG 检索相似 ID，并回表获取完整记录。"""
    vec = _get_embedder().embed_query(query.strip())
    ids = _search_ids_by_vector(vec, k)
    if not ids:
        return []
    rows = _get_mcp_agents_by_ids(ids)
    by_id = {int(r["id"]): r for r in rows}
    out: List[Dict[str, Any]] = []
    for i in ids:
        r = by_id.get(int(i))
        if r:
            out.append(r)
    return out