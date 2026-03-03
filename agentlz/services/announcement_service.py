from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException
from agentlz.config.settings import get_settings
from agentlz.repositories import announcement_repository as repo
from agentlz.services import user_service
from agentlz.core.ws_manager import get_ws_manager


def _table_name() -> str:
    s = get_settings()
    return getattr(s, "announcement_table_name", "announcement")


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


def _ensure_target_allowed(target_tenant_id: str) -> None:
    if str(target_tenant_id).strip() == "":
        raise HTTPException(status_code=400, detail="缺少 tenant_id")
    if str(target_tenant_id) == "default":
        raise HTTPException(status_code=403, detail="default 为保留租户不可使用")


def _ensure_admin_for_target(
    *,
    target_tenant_id: str,
    claims: Optional[Dict[str, Any]],
    tenant_id: str,
) -> Dict[str, Any]:
    _ensure_target_allowed(target_tenant_id)
    user = _current_user(claims, tenant_id)
    if str(target_tenant_id) == "system":
        if not _is_system_admin(user):
            raise HTTPException(status_code=403, detail="仅 system 管理员可操作系统公告")
    else:
        if not _is_tenant_admin_for(user, target_tenant_id):
            raise HTTPException(status_code=403, detail="仅租户管理员可操作租户公告")
    return user or {}


def list_announcements_service(
    *,
    page: int,
    per_page: int,
    sort: str,
    order: str,
    q: Optional[str],
    type: str,
    tenant_id: str,
    claims: Optional[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int]:
    table = _table_name()
    user = _current_user(claims, tenant_id)
    if type == "system":
        if not _is_system_admin(user):
            raise HTTPException(status_code=403, detail="仅 system 管理员可查看系统公告")
        tid = "system"
    else:
        if not _is_tenant_admin_for(user, tenant_id):
            raise HTTPException(status_code=403, detail="仅租户管理员可查看租户公告")
        if tenant_id == "default":
            raise HTTPException(status_code=403, detail="default 为保留租户不可使用")
        tid = tenant_id
    rows, total = repo.list_announcements(
        page=page,
        per_page=per_page,
        sort=sort,
        order=order,
        q=q,
        tenant_id=tid,
        table_name=table,
    )
    for r in rows:
        if r.get("created_at") is not None:
            r["created_at"] = str(r["created_at"])
        if r.get("updated_at") is not None:
            r["updated_at"] = str(r["updated_at"])
    return rows, total


def get_announcement_service(
    *,
    announcement_id: int,
    tenant_id: str,
    claims: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    table = _table_name()
    row = repo.get_announcement_by_id(announcement_id=announcement_id, table_name=table)
    if not row:
        return None
    _ensure_admin_for_target(target_tenant_id=str(row.get("tenant_id") or ""), claims=claims, tenant_id=tenant_id)
    if row.get("created_at") is not None:
        row["created_at"] = str(row["created_at"])
    if row.get("updated_at") is not None:
        row["updated_at"] = str(row["updated_at"])
    return row


def create_announcement_service(
    *,
    payload: Dict[str, Any],
    tenant_id: str,
    claims: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    table = _table_name()
    target_tenant_id = str(payload.get("tenant_id") or "")
    user = _ensure_admin_for_target(
        target_tenant_id=target_tenant_id,
        claims=claims,
        tenant_id=tenant_id,
    )
    row = repo.create_announcement(
        payload={
            "tenant_id": target_tenant_id,
            "title": payload.get("title"),
            "content": payload.get("content"),
            "disabled": bool(payload.get("disabled")),
            "created_by_id": user.get("id"),
            "updated_by_id": user.get("id"),
        },
        table_name=table,
    )
    if row.get("created_at") is not None:
        row["created_at"] = str(row["created_at"])
    if row.get("updated_at") is not None:
        row["updated_at"] = str(row["updated_at"])
    _publish_announcement(row)
    return row


def update_announcement_service(
    *,
    announcement_id: int,
    payload: Dict[str, Any],
    tenant_id: str,
    claims: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    table = _table_name()
    row = repo.get_announcement_by_id(announcement_id=announcement_id, table_name=table)
    if not row:
        return None
    user = _ensure_admin_for_target(
        target_tenant_id=str(row.get("tenant_id") or ""),
        claims=claims,
        tenant_id=tenant_id,
    )
    updated = repo.update_announcement(
        announcement_id=announcement_id,
        payload={
            "title": payload.get("title"),
            "content": payload.get("content"),
            "disabled": payload.get("disabled"),
            "updated_by_id": user.get("id"),
        },
        table_name=table,
    )
    if not updated:
        return None
    if updated.get("created_at") is not None:
        updated["created_at"] = str(updated["created_at"])
    if updated.get("updated_at") is not None:
        updated["updated_at"] = str(updated["updated_at"])
    _publish_announcement(updated)
    return updated


def delete_announcement_service(
    *,
    announcement_id: int,
    tenant_id: str,
    claims: Optional[Dict[str, Any]],
) -> bool:
    table = _table_name()
    row = repo.get_announcement_by_id(announcement_id=announcement_id, table_name=table)
    if not row:
        return False
    _ensure_admin_for_target(
        target_tenant_id=str(row.get("tenant_id") or ""),
        claims=claims,
        tenant_id=tenant_id,
    )
    ok = repo.delete_announcement(announcement_id=announcement_id, table_name=table)
    if ok:
        _publish_announcement_deleted(row)
    return ok


def list_visible_announcements_service(
    *,
    tenant_id: str,
    limit: int,
) -> List[Dict[str, Any]]:
    table = _table_name()
    rows = repo.list_visible_announcements(tenant_id=tenant_id, limit=limit, table_name=table)
    for r in rows:
        if r.get("created_at") is not None:
            r["created_at"] = str(r["created_at"])
        if r.get("updated_at") is not None:
            r["updated_at"] = str(r["updated_at"])
    return rows


def _publish_announcement(row: Dict[str, Any]) -> None:
    tenant_id = str(row.get("tenant_id") or "")
    payload = {"type": "announcement.updated", "topic": _topic_for_tenant(tenant_id), "data": row}
    manager = get_ws_manager()
    if tenant_id == "system":
        manager.submit(manager.broadcast_all(payload))
        return
    if tenant_id:
        manager.submit(manager.broadcast_tenant(tenant_id, payload))


def _publish_announcement_deleted(row: Dict[str, Any]) -> None:
    tenant_id = str(row.get("tenant_id") or "")
    payload = {
        "type": "announcement.deleted",
        "topic": _topic_for_tenant(tenant_id),
        "data": {"id": row.get("id"), "tenant_id": tenant_id},
    }
    manager = get_ws_manager()
    if tenant_id == "system":
        manager.submit(manager.broadcast_all(payload))
        return
    if tenant_id:
        manager.submit(manager.broadcast_tenant(tenant_id, payload))


def _topic_for_tenant(tenant_id: str) -> str:
    if tenant_id == "system":
        return "announcement:system"
    return f"announcement:tenant:{tenant_id}"
