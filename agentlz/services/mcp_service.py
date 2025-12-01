from typing import Any, Dict, Optional, List
from math import floor
from agentlz.schemas.check import ToolAssessment

from agentlz.core.embedding_model_factory import get_hf_embeddings
from agentlz.repositories.mcp_repository import (
    create_mcp_agent as _create_mysql_mcp,
    update_mcp_agent as _update_mysql_mcp,
    get_mcp_agents_by_ids as _get_mcp_agents_by_ids,
)
from agentlz.repositories.pg_mcp_repository import (
    search_mcp_hybrid_pg as _search_hybrid,
    upsert_mcp_agent_vector as _upsert_mcp_vector,
    search_ids_by_vector as _search_ids_by_vector,
    update_trust_score_pg as _update_trust_pg,
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
    _upsert_mcp_vector(
        int(row.get("id")),
        row.get("name") or "",
        row.get("transport") or "",
        row.get("command") or "",
        row.get("description") or "",
        row.get("category") or "",
        vec,
    )
    try:
        ts = float(row.get("trust_score", 0) or 0)
        if ts < 0:
            ts = 0.0
        if ts > 100:
            ts = 100.0
        _update_trust_pg(int(row.get("id")), ts)
    except Exception:
        pass
    return row


def update_mcp_agent_service(agent_id: int, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """更新 MCP 代理（MySQL），若描述/分类/传输/命令变更则重新嵌入并同步 PG。"""
    need_vector_sync = any(k in payload for k in ("description", "category", "transport", "command"))
    row = _update_mysql_mcp(agent_id, payload)
    if row and need_vector_sync:
        text = (row.get("description") or "") + " " + (row.get("category") or "")
        vec = _get_embedder().embed_query(text.strip())
        _upsert_mcp_vector(
            int(row.get("id")),
            row.get("name") or "",
            row.get("transport") or "",
            row.get("command") or "",
            row.get("description") or "",
            row.get("category") or "",
            vec,
        )
    if row and ("trust_score" in payload and payload["trust_score"] is not None):
        try:
            ts = float(row.get("trust_score", 0) or 0)
            if ts < 0:
                ts = 0.0
            if ts > 100:
                ts = 100.0
            _update_trust_pg(int(row.get("id")), ts)
        except Exception:
            pass
    return row

def search_mcp_agents_service(
    query: str,
    *,
    tenant_id: str = "default",
    alpha: float | None = None,
    theta: float | None = None,
    N: int | None = None,
    k: int | None = None,
) -> List[Dict[str, Any]]:
    """混合排序查询：语义 Top-N → 归一化 → 融合打分 → 语义门槛 → Top-k

    参数优先级：函数入参 > 配置默认值（settings.mcp_search_*）
    """
    from agentlz.config.settings import get_settings
    s = get_settings()
    a = float(alpha if alpha is not None else s.mcp_search_alpha)
    t = float(theta if theta is not None else s.mcp_search_theta)
    n = int(N if N is not None else s.mcp_search_topn)
    kk = int(k if k is not None else s.mcp_search_topk)
    vec = _get_embedder().embed_query(query.strip())
    return _search_hybrid(tenant_id=tenant_id, query_vec=vec, alpha=a, theta=t, N=n, k=kk)


def update_trust_by_tool_assessments(assessments: List[ToolAssessment], name_to_id: Dict[str, int]) -> None:
    ids: List[int] = []
    id_map: Dict[int, ToolAssessment] = {}
    for ta in assessments:
        agent_id: Optional[int] = None
        mid = str(getattr(ta, "mcp_id", "")).strip()
        if mid.isdigit():
            agent_id = int(mid)
        else:
            key1 = mid
            key2 = str(getattr(ta, "server", "")).strip()
            agent_id = name_to_id.get(key1) or name_to_id.get(key2)
        if agent_id is not None:
            ids.append(agent_id)
            id_map[agent_id] = ta
    if not ids:
        return
    rows = _get_mcp_agents_by_ids(ids)
    cur: Dict[int, float] = {int(r.get("id")): float(r.get("trust_score", 0) or 0) for r in rows}
    for agent_id in ids:
        ta = id_map.get(agent_id)
        if not ta:
            continue
        s = int(getattr(ta, "micro_score", 0) or 0)
        st = str(getattr(ta, "status", "")).lower()
        if st == "error":
            s = min(s, 30)
        elif st == "skipped":
            s = min(s, 60)
        prev = float(cur.get(agent_id, 0))
        alpha = 0.2
        new_score = floor((1 - alpha) * prev + alpha * s)
        if new_score < 0:
            new_score = 0
        if new_score > 100:
            new_score = 100
        update_mcp_agent_service(agent_id, {"trust_score": new_score})
        try:
            _update_trust_pg(agent_id, float(new_score))
        except Exception:
            pass
