from __future__ import annotations
import queue
from typing import Any, Dict, List, Optional, Tuple, Iterator
from fastapi import HTTPException
from sqlalchemy import text

from agentlz.config.settings import get_settings
from agentlz.core.database import get_mysql_engine
from agentlz.core.logger import setup_logging
from agentlz.repositories import agent_repository as repo
from agentlz.repositories import user_repository as user_repo
from agentlz.repositories import agent_mcp_repository as mcp_rel_repo
from agentlz.repositories import agent_document_repository as doc_rel_repo
from agentlz.repositories import mcp_repository as mcp_repo
from agentlz.repositories import document_repository as doc_repo
from agentlz.services.rag.rag_service import agent_chat_get_rag
from agentlz.repositories import record_repository as record_repo
from langchain_core.prompts import ChatPromptTemplate
from agentlz.core.model_factory import get_model
from agentlz.prompts.rag.rag import RAG_ANSWER_SYSTEM_PROMPT
import uuid
import json
import time
from agentlz.services.cache_service import cache_set
from agentlz.core.external_services import publish_to_rabbitmq


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


def _process_agent_meta(agent: Dict[str, Any]) -> Dict[str, Any]:
    """处理agent的meta字段反序列化"""
    if "meta" in agent and agent["meta"] is not None:
        try:
            if isinstance(agent["meta"], str):
                agent["meta"] = json.loads(agent["meta"])
        except (json.JSONDecodeError, TypeError):
            # 如果解析失败，保持原样
            pass
    return agent


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
    user_info = user_repo.get_user_by_id(
        user_id=current_user_id, tenant_id=tenant_id, table_name=user_table)
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
    user_info = user_repo.get_user_by_id(
        user_id=uid, tenant_id=tenant_id, table_name=user_table)
    agent_tenant_id = str((user_info or {}).get("tenant_id") or "default")
    agent_table = _tables()["agent"]
    row = repo.create_agent(
        payload={
            "name": payload.get("name"),
            "description": payload.get("description"),
            "api_name": None,
            "api_key": None,
            "system_prompt": payload.get("system_prompt"),
            "meta": payload.get("meta"),
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
            mcp_rel_repo.create_agent_mcp(payload={"agent_id": int(
                row["id"]), "mcp_agent_id": mid_int}, table_name=_tables()["agent_mcp"])
    if doc_ids:
        seen_d: set[str] = set()
        for did in doc_ids:
            did_str = str(did)
            if did_str in seen_d:
                continue
            seen_d.add(did_str)
            doc_rel_repo.create_agent_document(payload={"agent_id": int(
                row["id"]), "document_id": did_str}, table_name=_tables()["agent_document"])
    return _process_agent_meta(row)


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
    row = repo.get_agent_by_id_any_tenant(
        agent_id=agent_id, table_name=agent_table)
    if not row:
        return None
    if not _check_agent_permission(row, uid, tenant_id):
        raise HTTPException(status_code=403, detail="没有权限")
    update_payload: Dict[str, Any] = {}
    if "name" in payload:
        update_payload["name"] = payload.get("name")
    if "description" in payload:
        update_payload["description"] = payload.get("description")
    if "system_prompt" in payload:
        update_payload["system_prompt"] = payload.get("system_prompt")
    if "meta" in payload:
        update_payload["meta"] = payload.get("meta")
    if "disabled" in payload and payload["disabled"] is not None:
        update_payload["disabled"] = bool(payload.get("disabled"))
    update_payload["updated_by_id"] = uid
    updated = repo.update_agent(agent_id=agent_id, payload=update_payload, tenant_id=str(
        row.get("tenant_id") or tenant_id), table_name=agent_table)
    mcp_ids = payload.get("mcp_agent_ids")
    if isinstance(mcp_ids, list):
        current = mcp_rel_repo.list_agent_mcp(
            agent_id=agent_id, table_name=_tables()["agent_mcp"])
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
            mcp_rel_repo.create_agent_mcp(payload={
                                          "agent_id": agent_id, "mcp_agent_id": mid}, table_name=_tables()["agent_mcp"])
        for mid in to_del:
            mcp_rel_repo.delete_agent_mcp_by_pair(
                agent_id=agent_id, mcp_agent_id=mid, table_name=_tables()["agent_mcp"])
    doc_ids = payload.get("document_ids")
    if isinstance(doc_ids, list):
        current_d = doc_rel_repo.list_agent_documents(
            agent_id=agent_id, table_name=_tables()["agent_document"])
        current_doc_ids = {str(x.get("document_id")) for x in current_d}
        target_doc_ids: set[str] = {str(x) for x in doc_ids}
        to_add_d = target_doc_ids - current_doc_ids
        to_del_d = current_doc_ids - target_doc_ids
        for did in to_add_d:
            doc_rel_repo.create_agent_document(payload={
                                               "agent_id": agent_id, "document_id": did}, table_name=_tables()["agent_document"])
        for did in to_del_d:
            doc_rel_repo.delete_agent_document_by_pair(
                agent_id=agent_id, document_id=did, table_name=_tables()["agent_document"])
    
    # 返回更新后的agent信息，处理meta字段反序列化
    if updated:
        updated_agent = repo.get_agent_by_id_any_tenant(agent_id=agent_id, table_name=agent_table)
        return _process_agent_meta(dict(updated_agent)) if updated_agent else None
    return None


def update_agent_api_keys_service(*, agent_id: int, api_name: Optional[str], api_key: Optional[str], tenant_id: str, claims: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    _ensure_authenticated(claims)
    uid = _current_user_id(claims)
    agent_table = _tables()["agent"]
    row = repo.get_agent_by_id_any_tenant(agent_id=agent_id, table_name=agent_table)
    if not row:
        return None
    created_by_id = int(row.get("created_by_id") or 0)
    agent_tid = str(row.get("tenant_id") or "")
    user_role = str(row.get("user_role") or "")
    user_tid = str(row.get("user_tenant_id") or "")
    user_perm = str(row.get("user_perm") or "")
    allowed = False
    if created_by_id == uid:
        allowed = True
    elif user_role == "admin" and agent_tid != "default" and user_tid == agent_tid:
        allowed = True
    elif user_role == "user" and user_perm in ("admin", "write"):
        allowed = True
    if not allowed:
        raise HTTPException(status_code=403, detail="没有权限")
    payload = {"api_name": api_name, "api_key": api_key, "updated_by_id": uid}
    ok = repo.update_agent_no_read(agent_id=agent_id, payload=payload, tenant_id=agent_tid or tenant_id, table_name=agent_table)
    if not ok:
        return None
    return {"id": int(agent_id), "api_name": api_name, "updated_by_id": uid}


def delete_agent_service(*, agent_id: int, tenant_id: str, claims: Optional[Dict[str, Any]] = None) -> bool:
    _ensure_authenticated(claims)
    uid = _current_user_id(claims)
    agent_table = _tables()["agent"]
    row = repo.get_agent_by_id_any_tenant(
        agent_id=agent_id, table_name=agent_table)
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
    user_info = user_repo.get_user_by_id(
        user_id=uid, tenant_id=tenant_id, table_name=user_table)
    agent_table = _tables()["agent"]
    if type == "self":
        rows, total = repo.list_self_agents_agg(
            page=page,
            per_page=per_page,
            sort=sort,
            order=order,
            q=q,
            user_id=uid,
            agent_table_name=_tables()["agent"],
            mcp_rel_table_name=_tables()["agent_mcp"],
            mcp_table_name=getattr(s, "mcp_agents_table_name", "mcp_agents"),
            agent_doc_table_name=_tables()["agent_document"],
            doc_table_name=_tables()["doc"],
        )
    elif type == "tenant":
        user_tid = str((user_info or {}).get("tenant_id") or tenant_id)
        s_local = get_settings()
        rows, total = repo.list_agents_agg(
            page=page,
            per_page=per_page,
            sort=sort,
            order=order,
            q=q,
            tenant_id=user_tid,
            agent_table_name=_tables()["agent"],
            mcp_rel_table_name=_tables()["agent_mcp"],
            mcp_table_name=getattr(s_local, "mcp_agents_table_name", "mcp_agents"),
            agent_doc_table_name=_tables()["agent_document"],
            doc_table_name=_tables()["doc"],
        )
    else:
        raise HTTPException(status_code=400, detail="type 必须是 'self' 或 'tenant'")
    for r in rows:
        r.pop("api_name", None)
        r.pop("api_key", None)
        # 处理meta字段反序列化
        _process_agent_meta(r)
        mcp_ids_str = str(r.get("mcp_ids") or "")
        mcp_names_str = str(r.get("mcp_names") or "")
        doc_ids_str = str(r.get("doc_ids") or "")
        doc_titles_str = str(r.get("doc_titles") or "")
        sep = "|~|"
        mcp_ids = [x for x in mcp_ids_str.split(sep) if x] if mcp_ids_str else []
        mcp_names = [x for x in mcp_names_str.split(sep) if x] if mcp_names_str else []
        r["mcp_agents"] = [{"id": int(mcp_ids[i]), "name": mcp_names[i] if i < len(mcp_names) else ""} for i in range(len(mcp_ids))]
        doc_ids = [x for x in doc_ids_str.split(sep) if x] if doc_ids_str else []
        doc_titles = [x for x in doc_titles_str.split(sep) if x] if doc_titles_str else []
        r["documents"] = [{"id": doc_ids[i], "name": doc_titles[i] if i < len(doc_titles) else ""} for i in range(len(doc_ids))]
        r.pop("mcp_ids", None)
        r.pop("mcp_names", None)
        r.pop("doc_ids", None)
        r.pop("doc_titles", None)
    return rows, total


def list_accessible_agents_service(
    *,
    page: int,
    per_page: int,
    sort: str,
    order: str,
    q: Optional[str],
    tenant_id: str,
    claims: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """按当前用户可见权限分页列出所有智能体（不区分 type）。
    参数：
    - page/per_page/sort/order/q：分页与排序参数，支持名称模糊查询
    - tenant_id：请求所属租户（用于解析用户信息）
    - claims：鉴权信息（必须）
    行为：
    - 聚合“自己创建 + 管理员同租户且非 default + 授权表 admin/write”三类可见范围
    - 返回同时附带 MCP 与文档的简要聚合信息
    安全：
    - 仅在鉴权通过后执行查询；隐藏敏感字段（api_name/api_key）
    """
    _ensure_authenticated(claims)
    uid = _current_user_id(claims)
    s = get_settings()
    user_table = getattr(s, "user_table_name", "users")
    user_info = user_repo.get_user_by_id(
        user_id=uid, tenant_id=tenant_id, table_name=user_table)
    # 提取用户角色与租户，用于权限判定
    user_role = str((user_info or {}).get("role") or "")
    user_tid = str((user_info or {}).get("tenant_id") or tenant_id)
    agent_table = _tables()["agent"]
    perm_table = _tables()["user_agent_perm"]
    rows, total = repo.list_accessible_agents_by_user(
        page=page,
        per_page=per_page,
        sort=sort,
        order=order,
        q=q,
        user_id=uid,
        user_role=user_role,
        user_tenant_id=user_tid,
        agent_table_name=agent_table,
        user_agent_perm_table_name=perm_table,
    )
    accessible_agents=[]
    for r in rows:
        # 隐藏敏感字段
        r.pop("api_name", None)
        r.pop("api_key", None)
        # 处理meta字段反序列化
        _process_agent_meta(r)
        rel_m = mcp_rel_repo.list_agent_mcp(agent_id=int(r.get("id")), table_name=_tables()[
                                            "agent_mcp"]) if r.get("id") is not None else []
        m_ids = [int(x.get("mcp_agent_id"))
                     for x in rel_m if x.get("mcp_agent_id") is not None]
        m_rows = mcp_repo.get_mcp_agents_by_ids(m_ids) if m_ids else []
        r["mcp_agents"] = [{"id": int(x["id"]), "name": str(
            x.get("name") or "")} for x in m_rows]
        rel_d = doc_rel_repo.list_agent_documents(agent_id=int(r.get("id")), table_name=_tables()[
                                                  "agent_document"]) if r.get("id") is not None else []
        d_ids = [str(x.get("document_id"))
                     for x in rel_d if x.get("document_id")]
        doc_items: List[Dict[str, Any]] = []
        for did in d_ids:
            d = doc_repo.get_document_with_names_by_id_any_tenant(doc_id=did, table_name=_tables(
            )["doc"], user_table_name=_tables()["user"], tenant_table_name=_tables()["tenant"]) or {}
            doc_items.append({"id": did, "name": str(d.get("title") or "")})
        r["documents"] = doc_items
        # 过滤掉 disabled 为 True 的智能体
        if not r.get("disabled") :
            accessible_agents.append(r)
    return accessible_agents, len(accessible_agents)


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
    row = repo.get_agent_by_id_any_tenant(
        agent_id=agent_id, table_name=agent_table)
    if not row:
        return None
    if not _check_agent_permission(row, uid, tenant_id):
        raise HTTPException(status_code=403, detail="没有权限")
    return _process_agent_meta(dict(row))


def set_agent_mcp_allow_service(*, agent_id: int, mcp_agent_ids: List[int], tenant_id: str, claims: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    _ensure_authenticated(claims)
    uid = _current_user_id(claims)
    agent_table = _tables()["agent"]
    row = repo.get_agent_by_id_any_tenant(agent_id=agent_id, table_name=agent_table)
    if not row:
        raise HTTPException(status_code=404, detail="Agent不存在")
    if not _check_agent_permission(row, uid, tenant_id):
        raise HTTPException(status_code=403, detail="没有权限")
    tbl = _tables()["agent_mcp"]
    try:
        mcp_rel_repo.clear_agent_mcp(agent_id=agent_id, table_name=tbl)
        uniq_ids: List[int] = []
        seen: set[int] = set()
        for x in mcp_agent_ids or []:
            try:
                xi = int(x)
            except Exception:
                continue
            if xi in seen:
                continue
            seen.add(xi)
            uniq_ids.append(xi)
        inserted = mcp_rel_repo.bulk_insert_agent_mcp(agent_id=agent_id, ids=uniq_ids, table_name=tbl, permission_type=None)
        return {"agent_id": int(agent_id), "affected": int(inserted), "mode": "ALLOW"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"设置勾选失败: {e}")


def set_agent_mcp_exclude_service(*, agent_id: int, mcp_agent_ids: List[int], tenant_id: str, claims: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    _ensure_authenticated(claims)
    uid = _current_user_id(claims)
    agent_table = _tables()["agent"]
    row = repo.get_agent_by_id_any_tenant(agent_id=agent_id, table_name=agent_table)
    if not row:
        raise HTTPException(status_code=404, detail="Agent不存在")
    if not _check_agent_permission(row, uid, tenant_id):
        raise HTTPException(status_code=403, detail="没有权限")
    tbl = _tables()["agent_mcp"]
    try:
        uniq_ids: List[int] = []
        seen: set[int] = set()
        for x in mcp_agent_ids or []:
            try:
                xi = int(x)
            except Exception:
                continue
            if xi in seen:
                continue
            seen.add(xi)
            uniq_ids.append(xi)
        inserted = mcp_rel_repo.bulk_insert_agent_mcp(agent_id=agent_id, ids=uniq_ids, table_name=tbl, permission_type="EXCLUDE")
        if inserted == 0 and len(uniq_ids) > 0:
            return {
                "agent_id": int(agent_id),
                "affected": 0,
                "mode": "EXCLUDE",
                "error": "agent_mcp 缺少列 permission_type/is_default，请执行: ALTER TABLE agent_mcp ADD COLUMN permission_type ENUM('ALLOW','EXCLUDE') NOT NULL DEFAULT 'ALLOW'; ALTER TABLE agent_mcp ADD COLUMN is_default TINYINT(1) NOT NULL DEFAULT 1;",
            }
        return {"agent_id": int(agent_id), "affected": int(inserted), "mode": "EXCLUDE"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"设置排除失败: {e}")


def reset_agent_mcp_service(*, agent_id: int, tenant_id: str, claims: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    _ensure_authenticated(claims)
    uid = _current_user_id(claims)
    agent_table = _tables()["agent"]
    row = repo.get_agent_by_id_any_tenant(agent_id=agent_id, table_name=agent_table)
    if not row:
        raise HTTPException(status_code=404, detail="Agent不存在")
    if not _check_agent_permission(row, uid, tenant_id):
        raise HTTPException(status_code=403, detail="没有权限")
    tbl = _tables()["agent_mcp"]
    try:
        deleted = mcp_rel_repo.clear_agent_mcp(agent_id=agent_id, table_name=tbl)
        return {"agent_id": int(agent_id), "affected": int(deleted), "mode": "RESET"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"恢复默认失败: {e}")


def ensure_agent_access_service(*, agent_id: int, tenant_id: str, claims: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    logger = setup_logging(level="DEBUG", name="agentlz.agent_service", prefix="[Agent 服务]")
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
    logger = setup_logging(level="DEBUG", name="agentlz.agent_service", prefix="[Agent 服务]")
    logger.debug(f"进入 [get_agent_by_api_credentials_service] api_name={api_name}")
    agent_table = _tables()["agent"]
    row = repo.get_agent_by_api_credentials_any_tenant(api_name=api_name, api_key=api_key, table_name=agent_table)
    if not row:
        logger.debug(f"完成 [get_agent_by_api_credentials_service] result=None")
        return None
    try:
        if int(row.get("disabled") or 0) == 1:
            logger.debug(f"完成 [get_agent_by_api_credentials_service] disabled=1")
            return None
    except Exception:
        pass
    logger.debug(f"完成 [get_agent_by_api_credentials_service] agent_id={row.get('id')}")
    return row


def persist_chat_to_cache_and_mq(*, agent_id: int, record_id: int, input_text: str, output_text: str, meta: Optional[Dict[str, Any]] = None, ttl: int = 3600) -> None:
    logger = setup_logging(level="DEBUG", name="agentlz.agent_service", prefix="[Agent 服务]")
    logger.debug(f"进入 [persist_chat_to_cache_and_mq] agent_id={agent_id} record_id={record_id}")
    try:
        ts = int(time.time())
    except Exception:
        ts = int(time.time())
    sid = uuid.uuid4().hex[:8]
    key = f"record:{int(agent_id)}:{int(record_id)}:{ts}:{sid}"
    payload = {
        "agent_id": int(agent_id),
        "record_id": int(record_id),
        "input": input_text,
        "output": output_text,
        "created_at": ts,
        "meta": meta,
    }
    try:
        cache_set(key, json.dumps(payload, ensure_ascii=False), expire=ttl)
    except Exception:
        pass
    try:
        publish_to_rabbitmq("chat_persist_tasks", {"redis_key": key, "agent_id": int(agent_id), "record_id": int(record_id), "session_id": key, "created_at": ts}, durable=True)
    except Exception:
        pass
    logger.debug(f"完成 [persist_chat_to_cache_and_mq] key={key}")


def agent_llm_answer_stream(*, agent_id: int, record_id: int, out: Dict[str, Any], meta: Optional[Dict[str, Any]] = None) -> Iterator[str]:
    """
    LLM 简单回答流式生成器（Answer 版）
    参数：
    - agent_id：智能体 ID
    - record_id：会话记录 ID
    - out：RAG 预处理结果（包含 message/doc/history）
    - meta：可选元信息
    返回：
    - 以 SSE（Server-Sent Events）格式逐帧返回字符串；末帧为 `[DONE]`
    说明：
    - 组装 `RAG_ANSWER_SYSTEM_PROMPT` 与用户消息/历史/候选文档
    - 使用流式模型按缓冲大小与时间阈值 flush，保持前端平滑渲染
    - 模型未配置时回退为直出文本（优先 message，其次 doc）
    - 完成后持久化输入/输出到缓存与消息队列，便于审计与检索
    """
    logger = setup_logging(level="DEBUG", name="agentlz.agent_service", prefix="[Agent 服务]")
    logger.debug(f"进入 [agent_llm_answer_stream] agent_id={agent_id} record_id={record_id}")
    settings = get_settings()
    llm = get_model(settings=settings, streaming=True)
    prompt = ChatPromptTemplate.from_messages([
        ("system", RAG_ANSWER_SYSTEM_PROMPT),
        ("human", "用户问题：{message}\n历史上下文：\n{history}\n候选文档：\n{doc}"),
    ])
    if llm is None:
        def _fallback() -> Iterator[str]:
            msg = str(out.get("message") or "")
            doc = str(out.get("doc") or "")
            content = msg if msg else (doc[:2000] if doc else "模型未配置")
            try:
                yield f"data: {json.dumps({'record_id': int(record_id)})}\n\n"
            except Exception:
                yield f"data: {json.dumps({'record_id': record_id})}\n\n"
            lines = content.split("\n")
            frame = "".join([f"data: {ln}\n" for ln in lines]) + "\n"
            yield frame
            persist_chat_to_cache_and_mq(agent_id=int(agent_id), record_id=int(record_id), input_text=str(out.get("message") or ""), output_text=content, meta=meta)
            yield "data: [DONE]\n\n"
            logger.debug(f"完成 [agent_llm_answer_stream] record_id={record_id}")
        return _fallback()
    chain = prompt | llm

    def _gen() -> Iterator[str]:
        acc = ""
        buf = ""
        last_emit = time.time()
        settings_local = settings
        FLUSH_MS = float(getattr(settings_local, "sse_flush_ms", 0.08) or 0.08)
        MAX_BUF = int(getattr(settings_local, "sse_max_buf", 64) or 64)
        try:
            yield f"data: {json.dumps({'record_id': int(record_id)})}\n\n"
        except Exception:
            yield f"data: {json.dumps({'record_id': record_id})}\n\n"
        try:
            for chunk in chain.stream({
                "message": str(out.get("message") or ""),
                "doc": str(out.get("doc") or ""),
                "history": str(out.get("history") or ""),
            }):
                try:
                    content = getattr(chunk, "content", str(chunk))
                except Exception:
                    content = str(chunk)
                if content:
                    acc += content
                    buf += content
                    now = time.time()
                    should_flush = (len(buf) >= MAX_BUF) or ("\n" in content) or ((now - last_emit) >= FLUSH_MS)
                    if should_flush and buf.strip() != "":
                        lines = buf.split("\n")
                        frame = "".join([f"data: {ln}\n" for ln in lines]) + "\n"
                        yield frame
                        buf = ""
                        last_emit = now
        except Exception:
            yield "data: 服务暂时不可用，请稍后重试\n\n"
        if buf.strip() != "":
            lines = buf.split("\n")
            frame = "".join([f"data: {ln}\n" for ln in lines]) + "\n"
            yield frame
        persist_chat_to_cache_and_mq(agent_id=int(agent_id), record_id=int(record_id), input_text=str(out.get("message") or ""), output_text=acc, meta=meta)
        yield "data: [DONE]\n\n"
        logger.debug(f"完成 [agent_llm_answer_stream] record_id={record_id}")
    return _gen()

def agent_llm_exe_stream(*, agent_id: int, record_id: int, out: Dict[str, Any], meta: Optional[Dict[str, Any]] = None) -> Iterator[str]:
    """
    LLM 执行流式生成器（MCP 版，SSE 事件）
    - 事件：chain.step/planner.plan/call.start/call.end/executor.summary/final
    - 帧格式：event/id/data（data 为 EventEnvelope JSON）
    - 文本类事件按缓冲阈值与时间阈值分块发送
    """
    from dataclasses import asdict
    from datetime import datetime, timezone, timedelta
    import threading
    import asyncio
    from uuid import uuid4
    from agentlz.schemas.events import EventEnvelope
    from agentlz.agents.planner.planner_agent import plan_workflow_chain
    from agentlz.agents.executor.executor_agnet import MCPChainExecutor
    from agentlz.schemas.workflow import WorkflowPlan, ExecutorTrace
    from langchain.agents import create_agent
    from agentlz.prompts.executor.executor import EXECUTOR_SYSTEM_PROMPT
    logger = setup_logging(level="DEBUG", name="agentlz.agent_service", prefix="[Agent 服务]")
    logger.debug(f"进入 [agent_llm_exe_stream] agent_id={agent_id} record_id={record_id}")
    settings = get_settings()
    FLUSH_MS = float(getattr(settings, "sse_flush_ms", 0.08) or 0.08)
    MAX_BUF = int(getattr(settings, "sse_max_buf", 64) or 64)
    trace_id = uuid4().hex
    seq = 1
    def _now() -> str:
        return datetime.now(timezone(timedelta(hours=8))).isoformat()
    def _to_payload(x: Any) -> Any:
        try:
            if hasattr(x, "model_dump"):
                return x.model_dump()
            if hasattr(x, "__dataclass_fields__"):
                return asdict(x)
            if isinstance(x, (dict, list, str, int, float)) or x is None:
                return x
            return str(x)
        except Exception:
            return str(x)
    def _sse(evt: str, payload: Any) -> str:
        nonlocal seq
        env = EventEnvelope(evt=evt, seq=seq, ts=_now(), trace_id=trace_id, payload=_to_payload(payload))
        seq += 1
        txt = json.dumps(env.model_dump(), ensure_ascii=False)
        return f"event: {evt}\nid: {env.seq}\ndata: {txt}\n\n"
    q: "queue.Queue[str]" = __import__("queue").Queue()
    DONE = "__SSE_DONE__"
    def _emit(evt: str, payload: Any) -> None:
        try:
            q.put_nowait(_sse(evt, payload))
        except Exception:
            pass
    def _emit_text(evt: str, text: str) -> None:
        buf = ""
        last_emit = time.time()
        for ln in str(text).split("\n"):
            buf += (ln + "\n")
            now = time.time()
            if (len(buf) >= MAX_BUF) or ((now - last_emit) >= FLUSH_MS) or ("\n" in ln):
                payload = buf.rstrip("\n")
                if payload.strip() != "":
                    _emit(evt, payload)
                buf = ""
                last_emit = now
        if buf.strip() != "":
            _emit(evt, buf)
    def _runner():
        try:
            user_input = str(out.get("message") or "") or str(out.get("doc") or "")
            if not user_input:
                _emit("final", "未提供可执行输入")
                q.put(DONE)
                return
            _emit("chain.step", "planner")
            plan = plan_workflow_chain(user_input)
            # 仅使用远程 MCP（http/sse），忽略 stdio
            try:
                remote_items = [item for item in getattr(plan, "mcp_config", []) or [] if str(getattr(item, "transport", "") or "").lower() in ("http", "sse")]
                if not remote_items:
                    _emit("executor.error", {"stage": "plan", "message": "计划不包含远程 MCP(http/sse) 工具"})
                    _emit_text("final", "执行失败：计划不包含远程 MCP(http/sse) 工具")
                    q.put(DONE)
                    return
                plan.mcp_config = remote_items
            except Exception as e:
                _emit("executor.error", {"stage": "plan", "message": f"解析计划失败：{e}"})
                _emit_text("final", f"执行失败：解析计划失败 {e}")
                q.put(DONE)
                return
            _emit("planner.plan", plan)
            _emit("chain.step", "executor")
            try:
                executor = MCPChainExecutor(plan if isinstance(plan, WorkflowPlan) else WorkflowPlan(execution_chain=[], mcp_config=[], instructions=""))
            except Exception as e:
                _emit("executor.error", {"stage": "init", "message": str(e)})
                _emit_text("final", f"执行器初始化失败：{e}")
                q.put(DONE)
                return
            try:
                executor.assemble_mcp()
                tools = []
                if getattr(executor, "client", None) is not None:
                    try:
                        tools = asyncio.run(executor.client.get_tools())
                    except Exception as e:
                        tools = []
                        _emit("executor.error", {"stage": "tools", "message": str(e)})
                # 若未加载到工具，直接给出错误并结束，避免误把计划文本当执行结果
                if not tools:
                    _emit("executor.error", {"stage": "tools", "message": "未加载到任何 MCP 工具"})
                    _emit_text("final", "执行失败：未加载到 MCP 工具")
                    q.put(DONE)
                    return
                # 使用执行器统一执行链（内部会收集工具调用日志）
                final_text = asyncio.run(executor.execute_chain(user_input))
                logs = getattr(executor, "last_calls", []) or []
                # 逐条推送工具级事件
                for c in logs:
                    _emit("call.start", {"name": str(c.get("name","")), "input": str(c.get("input",""))})
                    _emit("call.end", {"name": str(c.get("name","")), "output": str(c.get("output","")), "status": str(c.get("status","success"))})
                if logs:
                    rows = []
                    chain = getattr(plan, "execution_chain", []) or []
                    enriched = []
                    for i, c in enumerate(logs, 1):
                        server_name = chain[i - 1] if 0 <= (i - 1) < len(chain) else ""
                        cc = {**c, "server": server_name}
                        enriched.append(cc)
                        rows.append(f"{i:02d}. {c.get('name','')} -> {c.get('status','')}\n服务器: {server_name}\n输入: {c.get('input','')}\n输出: {c.get('output','')}")
                    chain_text = ", ".join(chain) if chain else ""
                    prefix = ("实际调用链:\n" + chain_text + "\n\n") if chain_text else ""
                    summary = (prefix + "工具调用摘要:\n" + "\n\n".join(rows)).strip()
                    _emit_text("executor.summary", summary)
                else:
                    _emit_text("executor.summary", "执行器完成，无工具调用日志。")
                _emit_text("final", str(final_text))
                try:
                    persist_chat_to_cache_and_mq(agent_id=int(agent_id), record_id=int(record_id), input_text=str(out.get("message") or ""), output_text=str(final_text), meta=meta)
                except Exception:
                    pass
            except Exception as e:
                _emit("executor.error", {"stage": "run", "message": str(e)})
                _emit_text("final", f"执行器运行失败：{e}")
        finally:
            try:
                q.put(DONE)
            except Exception:
                pass
    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    while True:
        try:
            frame = q.get()
        except Exception:
            break
        if frame == DONE:
            break
        yield frame

def agent_chat_service(*, agent_id: int, message: str, record_id: int = -1, meta: Optional[Dict[str, Any]] = None) -> Iterator[str]:
    logger = setup_logging(level="DEBUG", name="agentlz.agent_service", prefix="[Agent 服务]")
    logger.debug(f"进入 [agent_chat_service] agent_id={agent_id} record_id={record_id}")
    out = agent_chat_get_rag(agent_id=agent_id, message=message, record_id=record_id, meta=meta)
    try:
        record_id = int(out.get("record_id") or record_id)
    except Exception:
        pass
    logger.debug(f" 完成 [agent_chat_get_rag],  继续 [agent_chat_service] rag_ready record_id={record_id}")
    return agent_llm_answer_stream(agent_id=int(agent_id), record_id=int(record_id), out=out, meta=meta)
