from __future__ import annotations

from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request, Depends, Query, status
from agentlz.schemas.responses import Result
from agentlz.schemas.announcement import AnnouncementCreate, AnnouncementUpdate
from agentlz.services import announcement_service
from agentlz.app.deps.auth_deps import require_auth, require_tenant_id

router = APIRouter(prefix="/v1", tags=["announcement"])


@router.get("/announcements", response_model=Result)
def list_announcements(
    request: Request,
    claims: Dict[str, Any] = Depends(require_auth),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    sort: str = Query("id"),
    order: str = Query("DESC", regex="^(ASC|DESC)$"),
    q: Optional[str] = Query(None),
    type: str = Query("tenant", regex="^(system|tenant)$"),
):
    tenant_id = require_tenant_id(request)
    rows, total = announcement_service.list_announcements_service(
        page=page,
        per_page=per_page,
        sort=sort,
        order=order,
        q=q,
        type=type,
        tenant_id=tenant_id,
        claims=claims,
    )
    return Result.ok({"rows": rows, "total": total})


@router.get("/announcements/visible", response_model=Result)
def list_visible_announcements(
    request: Request,
    claims: Dict[str, Any] = Depends(require_auth),
    limit: int = Query(20, ge=1, le=100),
):
    tenant_id = require_tenant_id(request)
    rows = announcement_service.list_visible_announcements_service(tenant_id=tenant_id, limit=limit)
    return Result.ok({"rows": rows, "total": len(rows)})


@router.get("/announcements/{announcement_id:int}", response_model=Result)
def get_announcement(
    announcement_id: int,
    request: Request,
    claims: Dict[str, Any] = Depends(require_auth),
):
    tenant_id = require_tenant_id(request)
    row = announcement_service.get_announcement_service(
        announcement_id=announcement_id, tenant_id=tenant_id, claims=claims
    )
    if not row:
        raise HTTPException(status_code=404, detail="公告不存在")
    return Result.ok(row)


@router.post("/announcements", response_model=Result, status_code=status.HTTP_201_CREATED)
def create_announcement(
    payload: AnnouncementCreate,
    request: Request,
    claims: Dict[str, Any] = Depends(require_auth),
):
    tenant_id = require_tenant_id(request)
    row = announcement_service.create_announcement_service(
        payload=payload.model_dump(), tenant_id=tenant_id, claims=claims
    )
    return Result.ok(row)


@router.put("/announcements/{announcement_id:int}", response_model=Result)
def update_announcement(
    announcement_id: int,
    payload: AnnouncementUpdate,
    request: Request,
    claims: Dict[str, Any] = Depends(require_auth),
):
    tenant_id = require_tenant_id(request)
    row = announcement_service.update_announcement_service(
        announcement_id=announcement_id, payload=payload.model_dump(), tenant_id=tenant_id, claims=claims
    )
    if not row:
        raise HTTPException(status_code=404, detail="公告不存在或未变更")
    return Result.ok(row)


@router.delete("/announcements/{announcement_id:int}", response_model=Result)
def delete_announcement(
    announcement_id: int,
    request: Request,
    claims: Dict[str, Any] = Depends(require_auth),
):
    tenant_id = require_tenant_id(request)
    ok = announcement_service.delete_announcement_service(
        announcement_id=announcement_id, tenant_id=tenant_id, claims=claims
    )
    if not ok:
        raise HTTPException(status_code=404, detail="公告不存在")
    return Result.ok({"deleted": True})
