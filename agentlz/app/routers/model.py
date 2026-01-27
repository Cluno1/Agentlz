from __future__ import annotations
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request, Depends, Query, status
from agentlz.schemas.responses import Result
from agentlz.services import model_service
from agentlz.app.deps.auth_deps import require_auth, require_tenant_id, require_admin

router = APIRouter(prefix="/v1", tags=["models"])

@router.get("/models", response_model=Result)
def list_models(
    request: Request,
    claims: Dict[str, Any] = Depends(require_auth),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    sort: str = Query("id"),
    order: str = Query("DESC", regex="^(ASC|DESC)$"),
    q: Optional[str] = Query(None),
):
    tenant_id = require_tenant_id(request)
    rows, total = model_service.list_models(page=page, per_page=per_page, sort=sort, order=order, q=q)
    return Result.ok({"rows": rows, "total": total})

@router.get("/models/{model_id:int}", response_model=Result)
def get_model(model_id: int, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    require_tenant_id(request)
    row = model_service.get_model_by_id(model_id=model_id)
    if not row:
        raise HTTPException(status_code=404, detail="模型不存在")
    return Result.ok(row)

@router.post("/models", response_model=Result, status_code=status.HTTP_201_CREATED)
def create_model(payload: Dict[str, Any], request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    tenant_id = require_tenant_id(request)
    require_admin(claims, tenant_id)
    row = model_service.create_model(payload=payload or {})
    return Result.ok(row)

@router.put("/models/{model_id:int}", response_model=Result)
def update_model(model_id: int, payload: Dict[str, Any], request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    tenant_id = require_tenant_id(request)
    require_admin(claims, tenant_id)
    row = model_service.update_model(model_id=model_id, payload=payload or {})
    if not row:
        raise HTTPException(status_code=404, detail="模型不存在或未变更")
    return Result.ok(row)

@router.delete("/models/{model_id:int}", response_model=Result)
def delete_model(model_id: int, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    tenant_id = require_tenant_id(request)
    require_admin(claims, tenant_id)
    ok = model_service.delete_model(model_id=model_id)
    if not ok:
        raise HTTPException(status_code=404, detail="模型不存在")
    return Result.ok({"deleted": True})
