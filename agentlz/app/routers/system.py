from __future__ import annotations
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from agentlz.core.logger import setup_logging
from agentlz.schemas.responses import Result
from agentlz.services import tenant_service
from agentlz.app.deps.auth_deps import require_auth, require_tenant_id

logger = setup_logging()

router = APIRouter(prefix="/v1", tags=["system"])


@router.get("/system/tenants", response_model=Result)
def list_tenants(
    request: Request,
    claims: Dict[str, Any] = Depends(require_auth),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    sort: str = Query("id"),
    order: str = Query("DESC", regex="^(ASC|DESC)$"),
    q: Optional[str] = Query(None),
):
    tenant_id = require_tenant_id(request)
    user_id = claims.get("sub") if isinstance(claims, dict) else None
    logger.info(f"request {request.method} {request.url.path} page={page} per_page={per_page} sort={sort} order={order} q={q} tenant_id={tenant_id} user_id={user_id}")
    rows, total = tenant_service.list_tenants_service(page=page, per_page=per_page, sort=sort, order=order, q=q)
    return Result.ok({"rows": rows, "total": total})


@router.get("/system/tenants/{tenant_id}", response_model=Result)
def get_tenant(tenant_id: str, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    tid = require_tenant_id(request)
    user_id = claims.get("sub") if isinstance(claims, dict) else None
    logger.info(f"request {request.method} {request.url.path} tenant_id={tenant_id} header_tenant={tid} user_id={user_id}")
    row = tenant_service.get_tenant_service(tenant_id=tenant_id)
    if not row:
        raise HTTPException(status_code=404, detail="租户不存在")
    return Result.ok(row)


@router.post("/system/tenants", response_model=Result)
def create_tenant(payload: Dict[str, Any], request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    tid = require_tenant_id(request)
    user_id = claims.get("sub") if isinstance(claims, dict) else None
    log_payload = {k: ("******" if k in {"api_key"} else v) for k, v in (payload or {}).items()}
    logger.info(f"request {request.method} {request.url.path} tenant_id={tid} user_id={user_id} payload={log_payload}")
    row = tenant_service.create_tenant_service(payload=payload or {}, claims=claims, tenant_id=tid)
    return Result.ok(row)


@router.put("/system/tenants/{tenant_id}", response_model=Result)
def update_tenant(tenant_id: str, payload: Dict[str, Any], request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    tid = require_tenant_id(request)
    user_id = claims.get("sub") if isinstance(claims, dict) else None
    logger.info(f"request {request.method} {request.url.path} tenant_id={tenant_id} header_tenant={tid} user_id={user_id} payload={payload}")
    row = tenant_service.update_tenant_service(target_tenant_id=tenant_id, payload=payload or {}, claims=claims, tenant_id=tid)
    if not row:
        raise HTTPException(status_code=404, detail="租户不存在")
    return Result.ok(row)


@router.delete("/system/tenants/{tenant_id}", response_model=Result)
def delete_tenant(tenant_id: str, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    tid = require_tenant_id(request)
    user_id = claims.get("sub") if isinstance(claims, dict) else None
    logger.info(f"request {request.method} {request.url.path} tenant_id={tenant_id} header_tenant={tid} user_id={user_id}")
    ok = tenant_service.delete_tenant_service(target_tenant_id=tenant_id, claims=claims, tenant_id=tid)
    if not ok:
        raise HTTPException(status_code=404, detail="租户不存在")
    return Result.ok({})
