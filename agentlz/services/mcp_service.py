from typing import Any, Dict, Optional, List
from math import floor
from agentlz.schemas.check import ToolAssessment

from agentlz.core.embedding_model_factory import get_hf_embeddings
from agentlz.repositories.mcp_repository import (
    create_mcp_agent as _create_mysql_mcp,
    update_mcp_agent as _update_mysql_mcp,
    get_mcp_agents_by_ids as _get_mcp_agents_by_ids,
    get_mcp_agent_meta_by_id as _get_mcp_meta,
    update_mcp_tenant as _update_mcp_tenant,
    get_mcp_agents_by_unique as _get_by_unique,
)
from agentlz.repositories.pg_mcp_repository import (
    search_mcp_hybrid_pg as _search_hybrid,
    upsert_mcp_agent_vector as _upsert_mcp_vector,
    search_ids_by_vector as _search_ids_by_vector,
    update_trust_score_pg as _update_trust_pg,
    delete_mcp_agent_vector as _delete_vec,
)
from agentlz.repositories import user_repository as user_repo
from agentlz.repositories import mcp_repository as mcp_repo
from agentlz.repositories import agent_mcp_repository as mcp_rel_repo
from agentlz.config.settings import get_settings

_EMB = None

def _get_embedder():
    """获取并缓存嵌入模型，用于文本向量化。"""
    global _EMB
    if _EMB is None:
        _EMB = get_hf_embeddings()
    return _EMB

def _ensure_authenticated(claims: Optional[Dict[str, Any]]) -> None:
    if not claims or not isinstance(claims, dict):
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="缺少或非法的 Authorization 头")

def _current_user_id(claims: Optional[Dict[str, Any]]) -> int:
    if not claims or "sub" not in claims:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="无法获取用户身份信息")
    try:
        return int(claims["sub"])
    except Exception:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="无法获取用户身份信息")

def _check_mcp_permission(row: Dict[str, Any], current_user_id: int, tenant_id: str) -> bool:
    if not row:
        return False
    if int(row.get("created_by_id") or 0) == int(current_user_id):
        return True
    s = get_settings()
    user_table = getattr(s, "user_table_name", "users")
    user_info = user_repo.get_user_by_id(user_id=current_user_id, tenant_id=tenant_id, table_name=user_table)
    if not user_info:
        return False
    if str(user_info.get("role") or "") == "admin" and str(row.get("tenant_id") or "") != "default" and str(user_info.get("tenant_id") or "") == str(row.get("tenant_id") or ""):
        return True
    return False


def create_mcp_agent_service(payload: Dict[str, Any]) -> Dict[str, Any]:
    row: Dict[str, Any] = {}
    try:
        row = _create_mysql_mcp(payload)
    except Exception as e:
        msg = str(e)
        if ("Duplicate entry" in msg) or ("IntegrityError" in msg):
            triplets = [(str(payload.get("name") or ""), str(payload.get("transport") or ""), str(payload.get("command") or ""))]
            exist = _get_by_unique(triplets)
            if exist:
                row = exist[0]
            else:
                raise
        else:
            raise
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

def list_mcp_agents_service(
    *,
    page: int,
    per_page: int,
    sort: str,
    order: str,
    q: Optional[str],
    type: str,
    tenant_id: str,
    claims: Optional[Dict[str, Any]] = None,
) -> tuple[list[Dict[str, Any]], int]:
    _ensure_authenticated(claims)
    uid = _current_user_id(claims)
    if type == "self":
        rows, total = mcp_repo.list_mcp_self(user_id=uid, page=page, per_page=per_page, sort=sort, order=order, q=q)
        return rows, total
    if type == "tenant":
        rows, total = mcp_repo.list_mcp_tenant(tenant_id=tenant_id, page=page, per_page=per_page, sort=sort, order=order, q=q)
        return rows, total
    if type == "system":
        rows, total = mcp_repo.list_mcp_system(page=page, per_page=per_page, sort=sort, order=order, q=q)
        return rows, total
    from fastapi import HTTPException
    raise HTTPException(status_code=400, detail="type 必须是 'self' 或 'tenant' 或 'system'")

def get_mcp_agent_service(*, agent_id: int, tenant_id: str, claims: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    _ensure_authenticated(claims)
    uid = _current_user_id(claims)
    row = _get_mcp_meta(agent_id)
    if not row:
        return None
    tid = str(row.get("tenant_id") or "")
    if tid == "system" or tid == str(tenant_id) or (tid == "default" and int(row.get("created_by_id") or 0) == int(uid)):
        return row
    from fastapi import HTTPException
    raise HTTPException(status_code=403, detail="没有权限")

def update_mcp_agent_with_perm_service(*, agent_id: int, payload: Dict[str, Any], tenant_id: str, claims: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    _ensure_authenticated(claims)
    uid = _current_user_id(claims)
    row = _get_mcp_meta(agent_id)
    if not row:
        return None
    if not _check_mcp_permission(row, uid, tenant_id):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="没有权限")
    return update_mcp_agent_service(agent_id, payload)

def delete_mcp_agent_service(*, agent_id: int, tenant_id: str, claims: Optional[Dict[str, Any]] = None) -> bool:
    _ensure_authenticated(claims)
    uid = _current_user_id(claims)
    row = _get_mcp_meta(agent_id)
    if not row:
        return False
    if not _check_mcp_permission(row, uid, tenant_id):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="没有权限")
    ok = mcp_repo.delete_mcp_agent(agent_id)
    if ok:
        try:
            _delete_vec(agent_id)
        except Exception:
            pass
        try:
            s = get_settings()
            tbl = getattr(s, "agent_mcp_table_name", "agent_mcp")
            mcp_rel_repo.clear_agent_mcp_by_mcp_id(mcp_agent_id=agent_id, table_name=tbl)
        except Exception:
            pass
    return ok

def search_mcp_agents_service(
    query: str,
    *,
    tenant_id: str = "default",
    user_id: int | None = None,
    agent_id: int | None = None,
    alpha: float | None = None,
    theta: float | None = None,
    N: int | None = None,
    k: int | None = None,
) -> List[Dict[str, Any]]:
    """按查询语义检索 MCP，并在候选阶段进行权限剪枝。

    顺序：先计算可见集合（共享 ∪ 个人），融合 agent 勾选/排除差量 → 将 allowed_ids 传入 PG 候选 → 混合排序取 Top‑k。
    """
    """混合排序查询：语义 Top-N → 归一化 → 融合打分 → 语义门槛 → Top-k

    参数优先级：函数入参 > 配置默认值（settings.mcp_search_*）
    """
    from agentlz.config.settings import get_settings
    s = get_settings()
    a = float(alpha if alpha is not None else s.mcp_search_alpha)
    t = float(theta if theta is not None else s.mcp_search_theta)
    n = int(N if N is not None else s.mcp_search_topn)
    kk = int(k if k is not None else s.mcp_search_topk)
    from agentlz.repositories.mcp_repository import (
        list_visible_mcp_ids,
        list_agent_mcp_allow_ids,
        list_agent_mcp_exclude_ids,
    )
    vec = _get_embedder().embed_query(query.strip())
    allowed_ids: List[int] = []
    try:
        visible_ids = list_visible_mcp_ids(user_id, tenant_id)
        if agent_id is not None:
            allow_ids = list_agent_mcp_allow_ids(agent_id)
            exclude_ids = list_agent_mcp_exclude_ids(agent_id)
            if allow_ids:
                s = set(visible_ids)
                allowed_ids = [i for i in allow_ids if i in s]
            else:
                allowed_ids = list(visible_ids)
            if exclude_ids:
                ex = set(exclude_ids)
                allowed_ids = [i for i in allowed_ids if i not in ex]
        else:
            allowed_ids = list(visible_ids)
    except Exception:
        allowed_ids = []
    if not allowed_ids:
        return []
    rows = _search_hybrid(query_vec=vec, alpha=a, theta=t, N=n, k=kk, allowed_ids=allowed_ids)
    return rows

def share_mcp_agent_service(agent_id: int, user_id: int | None, tenant_id: str | None = None) -> Optional[Dict[str, Any]]:
    row = _get_mcp_meta(agent_id)
    if not row:
        return None
    creator = row.get("created_by_id")
    if str(creator) != str(user_id):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="仅创建者可共享")
    new_row = _update_mcp_tenant(agent_id, "system")
    return new_row


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
    from agentlz.config.settings import get_settings
    s = get_settings()
    alpha_cfg = float(getattr(s, "mcp_trust_update_alpha", 0.2))
    err_cap = int(getattr(s, "mcp_trust_error_cap", 30))
    skip_cap = int(getattr(s, "mcp_trust_skip_cap", 60))
    for agent_id in ids:
        ta = id_map.get(agent_id)
        if not ta:
            continue
        s = int(getattr(ta, "micro_score", 0) or 0)
        st = str(getattr(ta, "status", "")).lower()
        if st == "error":
            s = min(s, err_cap)
        elif st == "skipped":
            s = min(s, skip_cap)
        prev = float(cur.get(agent_id, 0))
        alpha = alpha_cfg
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
