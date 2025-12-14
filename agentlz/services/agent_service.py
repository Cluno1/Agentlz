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
    tbls = _tables()
    agent_table = tbls["agent"]
    user_table = tbls["user"]
    perm_table = tbls["user_agent_perm"]
    row = repo.get_agent_with_user_and_perm(agent_id=agent_id, user_id=uid, agent_table_name=agent_table, user_table_name=user_table, perm_table_name=perm_table)
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
    row = repo.get_agent_by_id_any_tenant(agent_id=agent_id, table_name=agent_table)
    if not row:
        return False
    if not _check_agent_permission(row, uid, tenant_id):
        raise HTTPException(status_code=403, detail="没有权限")
    return repo.delete_agent(agent_id=agent_id, tenant_id=str(row.get("tenant_id") or tenant_id), table_name=agent_table)




def list_agents_service_agg(
    *, page: int, per_page: int, sort: str, order: str, q: Optional[str], type: str, tenant_id: str, claims: Optional[Dict[str, Any]] = None
) -> Tuple[List[Dict[str, Any]], int]:
    _ensure_authenticated(claims)
    uid = _current_user_id(claims)
    s = get_settings()
    user_table = getattr(s, "user_table_name", "users")
    user_info = user_repo.get_user_by_id(user_id=uid, tenant_id=tenant_id, table_name=user_table)
    agent_table = _tables()["agent"]
    mcp_rel_tbl = _tables()["agent_mcp"]
    agent_doc_tbl = _tables()["agent_document"]
    doc_tbl = _tables()["doc"]
    mcp_tbl = "mcp_agents"
    if type == "tenant":
        user_tid = str((user_info or {}).get("tenant_id") or tenant_id)
        rows, total = repo.list_agents_agg(
            page=page,
            per_page=per_page,
            sort=sort,
            order=order,
            q=q,
            tenant_id=user_tid,
            agent_table_name=agent_table,
            mcp_rel_table_name=mcp_rel_tbl,
            mcp_table_name=mcp_tbl,
            agent_doc_table_name=agent_doc_tbl,
            doc_table_name=doc_tbl,
        )
    elif type == "self":
        rows, total = repo.list_self_agents_agg(
            page=page,
            per_page=per_page,
            sort=sort,
            order=order,
            q=q,
            user_id=uid,
            agent_table_name=agent_table,
            mcp_rel_table_name=mcp_rel_tbl,
            mcp_table_name=mcp_tbl,
            agent_doc_table_name=agent_doc_tbl,
            doc_table_name=doc_tbl,
        )
    else:
        raise HTTPException(status_code=400, detail="type 必须是 'self' 或 'tenant'")
    out_rows: List[Dict[str, Any]] = []
    for r in rows:
        m_ids_str = str(r.get("mcp_ids") or "")
        m_names_str = str(r.get("mcp_names") or "")
        d_ids_str = str(r.get("doc_ids") or "")
        d_titles_str = str(r.get("doc_titles") or "")
        m_ids = [x for x in m_ids_str.split(",") if x]
        m_names = [x for x in m_names_str.split(",")]
        d_ids = [x for x in d_ids_str.split(",") if x]
        d_titles = [x for x in d_titles_str.split(",")]
        m_list: List[Dict[str, Any]] = []
        for i in range(min(len(m_ids), len(m_names))):
            try:
                mid = int(m_ids[i])
            except Exception:
                continue
            m_list.append({"id": mid, "name": m_names[i]})
        d_list: List[Dict[str, Any]] = []
        for i in range(min(len(d_ids), len(d_titles))):
            d_list.append({"id": d_ids[i], "name": d_titles[i]})
        r2 = {k: v for k, v in r.items() if k not in {"api_name", "api_key", "mcp_ids", "mcp_names", "doc_ids", "doc_titles"}}
        r2["mcp_agents"] = m_list
        r2["documents"] = d_list
        out_rows.append(r2)
    return out_rows, total


def get_agent_service(*, agent_id: int, tenant_id: str, claims: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    _ensure_authenticated(claims)
    uid = _current_user_id(claims)
    agent_table = _tables()["agent"]
    row = repo.get_agent_by_id_any_tenant(agent_id=agent_id, table_name=agent_table)
    if not row:
        return None
    if not _check_agent_permission(row, uid, tenant_id):
        raise HTTPException(status_code=403, detail="没有权限")
    return row


def set_agent_mcp_allow_service(*, agent_id: int, mcp_agent_ids: List[int], tenant_id: str, claims: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """设置勾选的 MCP 列表（覆盖原有设置）。

    - 权限：创建者、管理员（同租户非 default）、或具备 write/admin 权限的用户。
    - 行为：清空现有关联，批量插入传入的 ID 作为允许集（不写 permission_type）。
    - 返回：{"agent_id": int, "affected": int, "mode": "ALLOW"}
    """
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
    """设置排除的 MCP 列表（增量排除）。

    - 依赖：表存在列 permission_type/is_default；否则返回 DDL 建议。
    - 行为：批量插入 EXCLUDE 行（不清空允许集）。
    - 返回：{"agent_id": int, "affected": int, "mode": "EXCLUDE"}
    """
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
    """恢复默认 MCP 配置（清空 agent_mcp）。

    - 行为：删除该 Agent 的所有关联行，恢复全量可用。
    - 返回：{"agent_id": int, "affected": int, "mode": "RESET"}
    """
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
