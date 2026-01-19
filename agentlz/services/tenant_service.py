from __future__ import annotations
from typing import Any, Dict, Optional, Tuple
from fastapi import HTTPException
from agentlz.config.settings import get_settings
from agentlz.repositories import tenant_repository as repo
from agentlz.services import user_service


def _table_name() -> str:
    s = get_settings()
    return getattr(s, "tenant_table_name", "tenant")


def _current_user(claims: Optional[Dict[str, Any]], tenant_id: str) -> Optional[Dict[str, Any]]:
    if not claims or "sub" not in claims:
        return None
    try:
        uid = int(claims.get("sub"))
    except Exception:
        return None
    return user_service.get_user_service(user_id=uid, tenant_id=tenant_id)


def _is_system_admin(user: Optional[Dict[str, Any]]) -> bool:
    if not user:
        return False
    return str(user.get("role") or "") == "admin" and str(user.get("tenant_id") or "") == "system"


def _is_tenant_admin_for(user: Optional[Dict[str, Any]], target_tenant_id: str) -> bool:
    if not user:
        return False
    return str(user.get("role") or "") == "admin" and str(user.get("tenant_id") or "") == str(target_tenant_id)


def _is_reserved(name: str) -> bool:
    return name in {"system", "default"}


def list_tenants_service(
    *,
    page: int,
    per_page: int,
    sort: str,
    order: str,
    q: Optional[str],
) -> Tuple[list[Dict[str, Any]], int]:
    table = _table_name()
    rows, total = repo.list_tenants(page=page, per_page=per_page, sort=sort, order=order, q=q, table_name=table)
    for r in rows:
        if r.get("created_at") is not None:
            r["created_at"] = str(r["created_at"])
        if r.get("updated_at") is not None:
            r["updated_at"] = str(r["updated_at"])
    return rows, total


def get_tenant_service(*, tenant_id: str) -> Optional[Dict[str, Any]]:
    table = _table_name()
    row = repo.get_tenant_by_id(tenant_id=tenant_id, table_name=table)
    if row:
        if row.get("created_at") is not None:
            row["created_at"] = str(row["created_at"])
        if row.get("updated_at") is not None:
            row["updated_at"] = str(row["updated_at"])
    return row


def create_tenant_service(*, payload: Dict[str, Any], claims: Optional[Dict[str, Any]], tenant_id: str) -> Dict[str, Any]:
    user = _current_user(claims, tenant_id)
    if not _is_system_admin(user):
        raise HTTPException(status_code=403, detail="仅 system 租户管理员可创建租户")
    name = str((payload or {}).get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="缺少租户名称")
    if _is_reserved(name):
        raise HTTPException(status_code=403, detail="保留租户不可创建")
    table = _table_name()
    exists = repo.get_tenant_by_name(name=name, table_name=table)
    if exists:
        raise HTTPException(status_code=400, detail="租户名称已存在")
    row = repo.create_tenant(payload={"id": payload.get("id"), "name": name, "disabled": bool(payload.get("disabled", False))}, table_name=table)
    if row.get("created_at") is not None:
        row["created_at"] = str(row["created_at"])
    if row.get("updated_at") is not None:
        row["updated_at"] = str(row["updated_at"])
    return row


def update_tenant_service(
    *,
    target_tenant_id: str,
    payload: Dict[str, Any],
    claims: Optional[Dict[str, Any]],
    tenant_id: str,
) -> Optional[Dict[str, Any]]:
    table = _table_name()
    current = _current_user(claims, tenant_id)
    row = repo.get_tenant_by_id(tenant_id=target_tenant_id, table_name=table)
    if not row:
        return None
    reserved = _is_reserved(str(row.get("name") or ""))
    can_system = _is_system_admin(current)
    can_self_admin = _is_tenant_admin_for(current, target_tenant_id)
    if not (can_system or can_self_admin):
        raise HTTPException(status_code=403, detail="无权限更新租户")
    if reserved and payload.get("disabled") is not None:
        raise HTTPException(status_code=403, detail="保留租户不可设置禁用")
    if not can_system and payload.get("disabled") is not None:
        raise HTTPException(status_code=403, detail="仅 system 管理员可设置禁用")
    new_name = payload.get("name")
    if new_name is not None and str(new_name).strip() != str(row.get("name") or ""):
        exists = repo.get_tenant_by_name(name=str(new_name).strip(), table_name=table)
        if exists:
            raise HTTPException(status_code=400, detail="租户名称已存在")
    updated = repo.update_tenant(tenant_id=target_tenant_id, payload={"name": payload.get("name"), "disabled": payload.get("disabled")}, table_name=table)
    if updated:
        if updated.get("created_at") is not None:
            updated["created_at"] = str(updated["created_at"])
        if updated.get("updated_at") is not None:
            updated["updated_at"] = str(updated["updated_at"])
    return updated


def delete_tenant_service(*, target_tenant_id: str, claims: Optional[Dict[str, Any]], tenant_id: str) -> bool:
    table = _table_name()
    current = _current_user(claims, tenant_id)
    row = repo.get_tenant_by_id(tenant_id=target_tenant_id, table_name=table)
    if not row:
        return False
    if _is_reserved(str(row.get("name") or "")):
        raise HTTPException(status_code=403, detail="保留租户不可删除")
    can_system = _is_system_admin(current)
    can_self_admin = _is_tenant_admin_for(current, target_tenant_id)
    if not (can_system or can_self_admin):
        raise HTTPException(status_code=403, detail="无权限删除租户")
    return repo.delete_tenant(tenant_id=target_tenant_id, table_name=table)
