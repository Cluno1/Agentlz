from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException
from sqlalchemy import text

from agentlz.config.settings import get_settings
from agentlz.core.database import get_mysql_engine
from agentlz.repositories import agent_repository as repo
from agentlz.repositories import user_repository as user_repo
from agentlz.repositories import agent_mcp_repository as mcp_rel_repo
from agentlz.repositories import agent_document_repository as doc_rel_repo
from agentlz.repositories import mcp_repository as mcp_repo
from agentlz.repositories import document_repository as doc_repo


def _ensure_authenticated(claims: Optional[Dict[str, Any]]) -> None:
    if not claims or not isinstance(claims, dict):
        raise HTTPException(status_code=401, detail="缺少或非法的 Authorization 头")


def _current_user_id(claims: Optional[Dict[str, Any]]) -> int:
    if not claims or "sub" not in claims:
        raise HTTPException(status_code=401, detail="无法获取用户身份信息")
    try:
        return int(claims["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="无法获取用户身份信息")


def _tables() -> Dict[str, str]:
    s = get_settings()
    return {
        "agent": getattr(s, "agent_table_name", "agent"),
        "agent_mcp": getattr(s, "agent_mcp_table_name", "agent_mcp"),
        "agent_document": getattr(s, "agent_document_table_name", "agent_document"),
        "user": getattr(s, "user_table_name", "users"),
        "doc": getattr(s, "document_table_name", "document"),
        "tenant": getattr(s, "tenant_table_name", "tenant"),
        "user_agent_perm": getattr(s, "user_agent_permission_table_name", "user_agent_permission"),
    }


def _check_agent_permission(agent: Dict[str, Any], current_user_id: int, tenant_id: str) -> bool:
    if not agent:
        return False
    if int(agent.get("created_by_id") or 0) == int(current_user_id):
        return True
    s = get_settings()
    user_table = getattr(s, "user_table_name", "users")
    user_info = user_repo.get_user_by_id(user_id=current_user_id, tenant_id=tenant_id, table_name=user_table)
    if not user_info:
        return False
    if str(user_info.get("role") or "") == "admin" and str(agent.get("tenant_id") or "") != "default" and str(user_info.get("tenant_id") or "") == str(agent.get("tenant_id") or ""):
        return True
    if str(user_info.get("role") or "") == "user":
        engine = get_mysql_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    f"SELECT perm FROM `{_tables()['user_agent_perm']}` WHERE user_id=:uid AND agent_id=:aid"
                ),
                {"uid": int(current_user_id), "aid": int(agent.get("id"))},
            ).mappings().first()
            if row and str(row.get("perm") or "") in ("admin", "write"):
                return True
    return False


def create_agent_service(*, payload: Dict[str, Any], tenant_id: str, claims: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    _ensure_authenticated(claims)
    uid = _current_user_id(claims)
    s = get_settings()
    user_table = getattr(s, "user_table_name", "users")
    user_info = user_repo.get_user_by_id(user_id=uid, tenant_id=tenant_id, table_name=user_table)
    agent_tenant_id = str((user_info or {}).get("tenant_id") or "default")
    agent_table = _tables()["agent"]
    row = repo.create_agent(
        payload={
            "name": payload.get("name"),
            "description": payload.get("description"),
            "api_name": None,
            "api_key": None,
            "created_by_id": uid,
            "disabled": bool(payload.get("disabled", False)),
        },
        tenant_id=agent_tenant_id,
        table_name=agent_table,
    )
    mcp_ids = payload.get("mcp_agent_ids") or []
    doc_ids = payload.get("document_ids") or []
    if mcp_ids:
        seen: set[int] = set()
        for mid in mcp_ids:
            try:
                mid_int = int(mid)
            except Exception:
                continue
            if mid_int in seen:
                continue
            seen.add(mid_int)
            mcp_rel_repo.create_agent_mcp(payload={"agent_id": int(row["id"]), "mcp_agent_id": mid_int}, table_name=_tables()["agent_mcp"])
    if doc_ids:
        seen_d: set[str] = set()
        for did in doc_ids:
            did_str = str(did)
            if did_str in seen_d:
                continue
            seen_d.add(did_str)
            doc_rel_repo.create_agent_document(payload={"agent_id": int(row["id"]), "document_id": did_str}, table_name=_tables()["agent_document"])
    return row


def update_agent_basic_service(*, agent_id: int, payload: Dict[str, Any], tenant_id: str, claims: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    更新智能体基本信息 任何 tenant_id 都可以
    - 创建者直接允许。
    - 管理员：当用户租户等于 agent 租户，且该租户不为 default 时允许。
    - 普通用户：查询 user_agent_permission ，若权限为 admin 或 write 允许。
    - 其他返回不允许。
    :param agent_id: 智能体ID
    :param payload: 更新 payload
    :param tenant_id: 租户ID
    :param claims: 认证信息
    :return: 更新后的智能体信息
    """
    _ensure_authenticated(claims)
    uid = _current_user_id(claims)
    agent_table = _tables()["agent"]
    row = repo.get_agent_by_id_any_tenant(agent_id=agent_id, table_name=agent_table)
    if not row:
        return None
    if not _check_agent_permission(row, uid, tenant_id):
        raise HTTPException(status_code=403, detail="没有权限")
    update_payload: Dict[str, Any] = {}
    if "name" in payload:
        update_payload["name"] = payload.get("name")
    if "description" in payload:
        update_payload["description"] = payload.get("description")
    if "disabled" in payload and payload["disabled"] is not None:
        update_payload["disabled"] = bool(payload.get("disabled"))
    update_payload["updated_by_id"] = uid
    updated = repo.update_agent(agent_id=agent_id, payload=update_payload, tenant_id=str(row.get("tenant_id") or tenant_id), table_name=agent_table)
    mcp_ids = payload.get("mcp_agent_ids")
    if isinstance(mcp_ids, list):
        current = mcp_rel_repo.list_agent_mcp(agent_id=agent_id, table_name=_tables()["agent_mcp"])
        current_ids = {int(x.get("mcp_agent_id")) for x in current}
        target_ids: set[int] = set()
        for x in mcp_ids:
            try:
                target_ids.add(int(x))
            except Exception:
                continue
        to_add = target_ids - current_ids
        to_del = current_ids - target_ids
        for mid in to_add:
            mcp_rel_repo.create_agent_mcp(payload={"agent_id": agent_id, "mcp_agent_id": mid}, table_name=_tables()["agent_mcp"])
        for mid in to_del:
            mcp_rel_repo.delete_agent_mcp_by_pair(agent_id=agent_id, mcp_agent_id=mid, table_name=_tables()["agent_mcp"])
    doc_ids = payload.get("document_ids")
    if isinstance(doc_ids, list):
        current_d = doc_rel_repo.list_agent_documents(agent_id=agent_id, table_name=_tables()["agent_document"])
        current_doc_ids = {str(x.get("document_id")) for x in current_d}
        target_doc_ids: set[str] = {str(x) for x in doc_ids}
        to_add_d = target_doc_ids - current_doc_ids
        to_del_d = current_doc_ids - target_doc_ids
        for did in to_add_d:
            doc_rel_repo.create_agent_document(payload={"agent_id": agent_id, "document_id": did}, table_name=_tables()["agent_document"])
        for did in to_del_d:
            doc_rel_repo.delete_agent_document_by_pair(agent_id=agent_id, document_id=did, table_name=_tables()["agent_document"])
    return updated


def update_agent_api_keys_service(*, agent_id: int, api_name: Optional[str], api_key: Optional[str], tenant_id: str, claims: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    _ensure_authenticated(claims)
    uid = _current_user_id(claims)
    agent_table = _tables()["agent"]
    row = repo.get_agent_by_id_any_tenant(agent_id=agent_id, table_name=agent_table)
    if not row:
        return None
    if not _check_agent_permission(row, uid, tenant_id):
        raise HTTPException(status_code=403, detail="没有权限")
    payload = {"api_name": api_name, "api_key": api_key, "updated_by_id": uid}
    return repo.update_agent(agent_id=agent_id, payload=payload, tenant_id=str(row.get("tenant_id") or tenant_id), table_name=agent_table)


def delete_agent_service(*, agent_id: int, tenant_id: str, claims: Optional[Dict[str, Any]] = None) -> bool:
    _ensure_authenticated(claims)
    uid = _current_user_id(claims)
    agent_table = _tables()["agent"]
    row = repo.get_agent_by_id_any_tenant(agent_id=agent_id, table_name=agent_table)
    if not row:
        return False
    if not _check_agent_permission(row, uid, tenant_id):
        raise HTTPException(status_code=403, detail="没有权限")
    return repo.delete_agent(agent_id=agent_id, tenant_id=str(row.get("tenant_id") or tenant_id), table_name=agent_table)


def _list_self_agents(*, page: int, per_page: int, sort: str, order: str, q: Optional[str], user_id: int, table_name: str) -> Tuple[List[Dict[str, Any]], int]:
    order_dir = "ASC" if str(order or "").upper() == "ASC" else "DESC"
    sort_col = sort if sort in {"id", "name", "description", "disabled", "created_at", "updated_at", "created_by_id", "updated_by_id"} else "id"
    offset = (page - 1) * per_page
    where = ["tenant_id = :tenant_id", "created_by_id = :uid"]
    params: Dict[str, Any] = {"tenant_id": "default", "uid": int(user_id)}
    if q:
        where.append("(name LIKE :q)")
        params["q"] = f"%{q}%"
    where_sql = "WHERE " + " AND ".join(where)
    count_sql = text(f"SELECT COUNT(*) AS cnt FROM `{table_name}` {where_sql}")
    list_sql = text(
        f"""
        SELECT id, name, description, tenant_id, created_at, created_by_id, updated_at, updated_by_id, disabled
        FROM `{table_name}`
        {where_sql}
        ORDER BY {sort_col} {order_dir}
        LIMIT :limit OFFSET :offset
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        total = conn.execute(count_sql, params).scalar() or 0
        rows = conn.execute(list_sql, {**params, "limit": per_page, "offset": offset}).mappings().all()
    return [dict(r) for r in rows], int(total)


def list_agents_service(
    *, page: int, per_page: int, sort: str, order: str, q: Optional[str], type: str, tenant_id: str, claims: Optional[Dict[str, Any]] = None
) -> Tuple[List[Dict[str, Any]], int]:
    _ensure_authenticated(claims)
    uid = _current_user_id(claims)
    s = get_settings()
    user_table = getattr(s, "user_table_name", "users")
    user_info = user_repo.get_user_by_id(user_id=uid, tenant_id=tenant_id, table_name=user_table)
    agent_table = _tables()["agent"]
    if type == "self":
        rows, total = _list_self_agents(page=page, per_page=per_page, sort=sort, order=order, q=q, user_id=uid, table_name=agent_table)
    elif type == "tenant":
        user_tid = str((user_info or {}).get("tenant_id") or tenant_id)
        rows, total = repo.list_agents(page=page, per_page=per_page, sort=sort, order=order, q=q, tenant_id=user_tid, table_name=agent_table)
    else:
        raise HTTPException(status_code=400, detail="type 必须是 'self' 或 'tenant'")
    for r in rows:
        r.pop("api_name", None)
        r.pop("api_key", None)
        rel_m = mcp_rel_repo.list_agent_mcp(agent_id=int(r.get("id")), table_name=_tables()["agent_mcp"]) if r.get("id") is not None else []
        m_ids = [int(x.get("mcp_agent_id")) for x in rel_m if x.get("mcp_agent_id") is not None]
        m_rows = mcp_repo.get_mcp_agents_by_ids(m_ids) if m_ids else []
        r["mcp_agents"] = [{"id": int(x["id"]), "name": str(x.get("name") or "")} for x in m_rows]
        rel_d = doc_rel_repo.list_agent_documents(agent_id=int(r.get("id")), table_name=_tables()["agent_document"]) if r.get("id") is not None else []
        d_ids = [str(x.get("document_id")) for x in rel_d if x.get("document_id")]
        doc_items: List[Dict[str, Any]] = []
        for did in d_ids:
            d = doc_repo.get_document_with_names_by_id_any_tenant(doc_id=did, table_name=_tables()["doc"], user_table_name=_tables()["user"], tenant_table_name=_tables()["tenant"]) or {}
            doc_items.append({"id": did, "name": str(d.get("title") or "")})
        r["documents"] = doc_items
    return rows, total


def get_agent_service(*, agent_id: int, tenant_id: str, claims: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """获取智能体详情（含权限校验）
    参数：
    - agent_id：智能体ID
    - tenant_id：当前请求所属租户ID（用于权限判定）
    - claims：鉴权信息（JWT声明）
    返回：
    - 若存在且有权限则返回智能体字典；否则返回 None 或抛出 403
    """
    _ensure_authenticated(claims)
    uid = _current_user_id(claims)
    agent_table = _tables()["agent"]
    row = repo.get_agent_by_id_any_tenant(agent_id=agent_id, table_name=agent_table)
    if not row:
        return None
    if not _check_agent_permission(row, uid, tenant_id):
        raise HTTPException(status_code=403, detail="没有权限")
    return row


def ensure_agent_access_service(*, agent_id: int, tenant_id: str, claims: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """确保智能体存在且用户有访问权限
    参数
    - agent_id：目标智能体 ID
    - tenant_id：当前请求的租户标识（用于权限判断）
    - claims：鉴权信息（JWT 声明的解析结果）
    返回
    - 存在且有权限访问的智能体行字典
    异常
    - `HTTPException(403)`：无操作权限
    - `HTTPException(401)`：鉴权缺失或非法（由内部工具抛出）
    - `HTTPException(404)`：智能体不存在
    """
    _ensure_authenticated(claims)
    uid = _current_user_id(claims)
    agent_table = _tables()["agent"]
    row = repo.get_agent_by_id_any_tenant(agent_id=agent_id, table_name=agent_table)
    if not row:
        raise HTTPException(status_code=404, detail="Agent不存在")
    if not _check_agent_permission(row, uid, tenant_id):
        raise HTTPException(status_code=403, detail="没有权限")
    return row

def get_agent_by_api_credentials_service(*, api_name: str, api_key: str) -> Optional[Dict[str, Any]]:
    """按 API 凭证查询智能体
    参数：
    - api_name：智能体在外部系统的 API 名称
    - api_key：智能体在外部系统的 API 密钥
    返回：
    - 若匹配成功且未被禁用，返回智能体字典；否则返回 None
    说明：
    - 此函数不进行用户权限校验，适用于凭证直连场景
    """
    agent_table = _tables()["agent"]
    row = repo.get_agent_by_api_credentials_any_tenant(api_name=api_name, api_key=api_key, table_name=agent_table)
    if not row:
        return None
    try:
        if int(row.get("disabled") or 0) == 1:
            return None
    except Exception:
        pass
    return row
    
