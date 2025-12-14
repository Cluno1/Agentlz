from __future__ import annotations
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, Depends, Query
from agentlz.schemas.responses import Result
from agentlz.services import mcp_service
from agentlz.app.deps.auth_deps import require_auth, require_tenant_id, require_admin

router = APIRouter(prefix="/v1", tags=["mcp"])


@router.post("/mcp", response_model=Result)
def create_mcp(
    payload: Dict[str, Any],
    request: Request,
    claims: Dict[str, Any] = Depends(require_auth),
    type: str = Query("self", regex="^(self|tenant|system)$"),
):
    uid = claims.get("sub") if isinstance(claims, dict) else None
    if type == "self":
        tenant_id = "default"
    elif type == "tenant":
        tenant_id = require_tenant_id(request)
        require_admin(claims, tenant_id)
    elif type == "system":
        tenant_id = "system"
    else:
        tenant_id = require_tenant_id(request)
    data: Dict[str, Any] = {}
    for k, v in (payload or {}).items():
        if v is not None:
            data[k] = v
    data["tenant_id"] = tenant_id
    data["created_by_id"] = uid
    row = mcp_service.create_mcp_agent_service(payload=data)
    return Result.ok(row)

@router.get("/mcp", response_model=Result)
def list_mcp(
    request: Request,
    claims: Dict[str, Any] = Depends(require_auth),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    sort: str = Query("id"),
    order: str = Query("DESC", regex="^(ASC|DESC)$"),
    q: Optional[str] = Query(None),
    type: str = Query("self", regex="^(self|tenant|system)$"),
):
    tenant_id = require_tenant_id(request)
    rows, total = mcp_service.list_mcp_agents_service(
        page=page, per_page=per_page, sort=sort, order=order, q=q, type=type, tenant_id=tenant_id, claims=claims
    )
    return Result.ok({"rows": rows, "total": total})

@router.get("/mcp/{agent_id:int}", response_model=Result)
def get_mcp(agent_id: int, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    tenant_id = require_tenant_id(request)
    row = mcp_service.get_mcp_agent_service(agent_id=agent_id, tenant_id=tenant_id, claims=claims)
    if not row:
        return Result.error(message="MCP不存在", code=404, data={})
    return Result.ok(row)

@router.put("/mcp/{agent_id:int}", response_model=Result)
def update_mcp(agent_id: int, payload: Dict[str, Any], request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    tenant_id = require_tenant_id(request)
    row = mcp_service.update_mcp_agent_with_perm_service(agent_id=agent_id, payload=payload, tenant_id=tenant_id, claims=claims)
    if not row:
        return Result.error(message="MCP不存在", code=404, data={})
    return Result.ok(row)

@router.delete("/mcp/{agent_id:int}", response_model=Result)
def delete_mcp(agent_id: int, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    tenant_id = require_tenant_id(request)
    ok = mcp_service.delete_mcp_agent_service(agent_id=agent_id, tenant_id=tenant_id, claims=claims)
    if not ok:
        return Result.error(message="MCP不存在或删除失败", code=404, data={})
    return Result.ok({})


@router.get("/mcp/search", response_model=Result)
def search_mcp(
    request: Request,
    claims: Dict[str, Any] = Depends(require_auth),
    q: str = Query(...),
    k: Optional[int] = Query(None, ge=1, le=100),
    agent_id: Optional[int] = Query(None, ge=1),
    alpha: Optional[float] = Query(None, ge=0.0, le=1.0),
    theta: Optional[float] = Query(None, ge=0.0, le=1.0),
    N: Optional[int] = Query(None, ge=1, le=1000),
):
    tenant_id = require_tenant_id(request)
    uid = claims.get("sub") if isinstance(claims, dict) else None
    rows = mcp_service.search_mcp_agents_service(
        query=q,
        tenant_id=tenant_id,
        user_id=uid,
        agent_id=agent_id,
        alpha=alpha,
        theta=theta,
        N=N,
        k=k,
    )
    return Result.ok(rows)

