from __future__ import annotations
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from agentlz.core.logger import setup_logging
from agentlz.schemas.responses import Result
from agentlz.services import agent_service
from agentlz.app.deps.auth_deps import require_auth, require_tenant_id
from agentlz.schemas.agent import AgentCreate, AgentUpdate, AgentApiUpdate

logger = setup_logging()


router = APIRouter(prefix="/v1", tags=["agents"])


@router.get("/agents", response_model=Result)
def list_agents(
    request: Request,
    claims: Dict[str, Any] = Depends(require_auth),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    sort: str = Query("id"),
    order: str = Query("DESC", regex="^(ASC|DESC)$"),
    q: Optional[str] = Query(None),
    type: str = Query("self", regex="^(self|tenant)$"),
):
    tenant_id = require_tenant_id(request)
    user_id = claims.get("sub") if isinstance(claims, dict) else None
    logger.info(
        f"request {request.method} {request.url.path} "
        f"page={page} per_page={per_page} sort={sort} order={order} q={q} type={type} "
        f"tenant_id={tenant_id} user_id={user_id}"
    )
    rows, total = agent_service.list_agents_service(
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


@router.get("/agents/{agent_id}", response_model=Result)
def get_agent(agent_id: int, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    tenant_id = require_tenant_id(request)
    user_id = claims.get("sub") if isinstance(claims, dict) else None
    logger.info(
        f"request {request.method} {request.url.path} agent_id={agent_id} "
        f"tenant_id={tenant_id} user_id={user_id}"
    )
    row = agent_service.get_agent_service(agent_id=agent_id, tenant_id=tenant_id, claims=claims)
    if not row:
        raise HTTPException(status_code=404, detail="Agent不存在")
    return Result.ok(row)


@router.post("/agents", response_model=Result)
def create_agent(payload: AgentCreate, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    tenant_id = require_tenant_id(request)
    user_id = claims.get("sub") if isinstance(claims, dict) else None
    payload_data = payload.model_dump(exclude_none=True)
    logger.info(
        f"request {request.method} {request.url.path} tenant_id={tenant_id} user_id={user_id} payload={payload_data}"
    )
    row = agent_service.create_agent_service(payload=payload_data, tenant_id=tenant_id, claims=claims)
    return Result.ok(row)


@router.put("/agents/{agent_id}", response_model=Result)
def update_agent(agent_id: int, payload: AgentUpdate, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    tenant_id = require_tenant_id(request)
    user_id = claims.get("sub") if isinstance(claims, dict) else None
    payload_data = payload.model_dump(exclude_none=True)
    logger.info(
        f"request {request.method} {request.url.path} agent_id={agent_id} tenant_id={tenant_id} user_id={user_id} payload={payload_data}"
    )
    row = agent_service.update_agent_basic_service(agent_id=agent_id, payload=payload_data, tenant_id=tenant_id, claims=claims)
    if not row:
        raise HTTPException(status_code=404, detail="Agent不存在")
    return Result.ok(row)


@router.put("/agents/{agent_id}/api", response_model=Result)
def update_agent_api(agent_id: int, payload: AgentApiUpdate, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    tenant_id = require_tenant_id(request)
    user_id = claims.get("sub") if isinstance(claims, dict) else None
    payload_log = {"api_name": payload.api_name, "api_key": "******" if payload.api_key else None}
    logger.info(
        f"request {request.method} {request.url.path} agent_id={agent_id} tenant_id={tenant_id} user_id={user_id} payload={payload_log}"
    )
    row = agent_service.update_agent_api_keys_service(
        agent_id=agent_id,
        api_name=payload.api_name,
        api_key=payload.api_key,
        tenant_id=tenant_id,
        claims=claims,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Agent不存在")
    return Result.ok(row)


@router.delete("/agents/{agent_id}", response_model=Result)
def delete_agent(agent_id: int, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    tenant_id = require_tenant_id(request)
    user_id = claims.get("sub") if isinstance(claims, dict) else None
    logger.info(
        f"request {request.method} {request.url.path} agent_id={agent_id} tenant_id={tenant_id} user_id={user_id}"
    )
    ok = agent_service.delete_agent_service(agent_id=agent_id, tenant_id=tenant_id, claims=claims)
    if not ok:
        raise HTTPException(status_code=404, detail="Agent不存在")
    return Result.ok({})