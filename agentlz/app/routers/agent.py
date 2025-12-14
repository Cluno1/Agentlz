from __future__ import annotations
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from agentlz.core.logger import setup_logging
from agentlz.schemas.responses import Result
from agentlz.services import agent_service, mcp_service
from agentlz.app.deps.auth_deps import require_auth, require_tenant_id, require_admin
from agentlz.schemas.agent import AgentCreate, AgentUpdate, AgentApiUpdate
from typing import List

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
    """分页查询智能体列表。

    参数：
    - `page`: 页码（从1开始）
    - `per_page`: 每页条数（1-100）
    - `sort`: 排序字段（默认 `id`）
    - `order`: 排序方向（`ASC` 或 `DESC`）
    - `q`: 关键词筛选（按名称）
    - `type`: 列表类型（`self` 仅返回本人 default 租户创建的；`tenant` 返回当前租户下的）

    权限：需要登录认证（Authorization）。

    返回：`Result({"rows": [...], "total": n})`。
    """
    tenant_id = require_tenant_id(request)
    user_id = claims.get("sub") if isinstance(claims, dict) else None
    logger.info(
        f"request {request.method} {request.url.path} "
        f"page={page} per_page={per_page} sort={sort} order={order} q={q} type={type} "
        f"tenant_id={tenant_id} user_id={user_id}"
    )
    rows, total = agent_service.list_agents_service_agg(
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
    """获取智能体详情。

    参数：
    - `agent_id`: 智能体ID（路径参数）

    权限：需要登录认证；创建者、同租户管理员（租户非 default）或具备写/管理权限的用户可访问。

    返回：`Result(row)`，未找到返回 404。
    """
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
def create_agent(
    payload: AgentCreate,
    request: Request,
    claims: Dict[str, Any] = Depends(require_auth),
    type: str = Query("self", regex="^(self|tenant)$"),
):
    """创建智能体。

    参数：
    - `payload`: 创建信息（`AgentCreate`）
    - `type`: 创建类型（`self` 写入 default；`tenant` 写入当前租户）

    权限：需要登录认证。

    返回：`Result(row)`，包含新建的智能体信息。
    """
    user_id = claims.get("sub") if isinstance(claims, dict) else None
    tenant_id = "default" if type == "self" else require_tenant_id(request)
    payload_data = payload.model_dump(exclude_none=True)
    logger.info(
        f"request {request.method} {request.url.path} type={type} tenant_id={tenant_id} user_id={user_id} payload={payload_data}"
    )
    row = agent_service.create_agent_service(payload=payload_data, tenant_id=tenant_id, claims=claims)
    return Result.ok(row)


@router.put("/agents/{agent_id}", response_model=Result)
def update_agent(agent_id: int, payload: AgentUpdate, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    """更新智能体基本信息。

    参数：
    - `agent_id`: 智能体ID（路径参数）
    - `payload`: 可更新字段（`AgentUpdate`），支持名称/描述/禁用，以及关联的文档与 MCP ID 列表。

    权限：需要登录认证；创建者、同租户管理员（租户非 default）或具备写/管理权限的用户可更新。

    返回：`Result(row)`，未找到返回 404。
    """
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
    """更新智能体的 API 名称与密钥。

    参数：
    - `agent_id`: 智能体ID（路径参数）
    - `payload`: `AgentApiUpdate`，包含 `api_name` 与 `api_key`（返回时不回显密钥）。

    权限：需要登录认证；创建者、同租户管理员（租户非 default）或具备写/管理权限的用户可更新。

    返回：`Result(row)`，未找到返回 404。
    """
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
    """删除智能体。

    参数：
    - `agent_id`: 智能体ID（路径参数）

    权限：需要登录认证；创建者、同租户管理员（租户非 default）或具备写/管理权限的用户可删除。

    返回：`Result({})`，未找到返回 404。
    """
    tenant_id = require_tenant_id(request)
    user_id = claims.get("sub") if isinstance(claims, dict) else None
    logger.info(
        f"request {request.method} {request.url.path} agent_id={agent_id} tenant_id={tenant_id} user_id={user_id}"
    )
    ok = agent_service.delete_agent_service(agent_id=agent_id, tenant_id=tenant_id, claims=claims)
    if not ok:
        raise HTTPException(status_code=404, detail="Agent不存在")
    return Result.ok({})


@router.put("/agents/{agent_id}/mcp/allow", response_model=Result)
def set_agent_mcp_allow(agent_id: int, payload: Dict[str, Any], request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    """设置允许的 MCP 工具列表（覆盖原有设置）。

    参数：
    - `agent_id`: 智能体ID（路径参数）
    - `payload`: 形如 `{"mcp_agent_ids": [23,45,...]}`

    权限：创建者、同租户管理员（租户非 default）、或具备 write/admin 权限的用户。

    返回：`Result({"agent_id": int, "affected": int, "mode": "ALLOW"})`。
    """
    # 勾选 MCP 列表，覆盖原有设置；仅创建者或有写权限的用户可操作
    # 请求体：{"mcp_agent_ids": [23,45,...]}
    # 返回：{"agent_id": int, "affected": 插入条数, "mode": "ALLOW"}
    tenant_id = require_tenant_id(request)
    user_id = claims.get("sub") if isinstance(claims, dict) else None
    ids: List[int] = []
    for x in (payload or {}).get("mcp_agent_ids", []) or []:
        try:
            ids.append(int(x))
        except Exception:
            continue
    logger.info(
        f"request {request.method} {request.url.path} agent_id={agent_id} tenant_id={tenant_id} user_id={user_id} allow_ids={ids}"
    )
    res = agent_service.set_agent_mcp_allow_service(agent_id=agent_id, mcp_agent_ids=ids, tenant_id=tenant_id, claims=claims)
    return Result.ok(res)


@router.put("/agents/{agent_id}/mcp/exclude", response_model=Result)
def set_agent_mcp_exclude(agent_id: int, payload: Dict[str, Any], request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    """设置排除的 MCP 工具列表（增量排除，不清空允许集）。

    参数：
    - `agent_id`: 智能体ID（路径参数）
    - `payload`: 形如 `{"mcp_agent_ids": [23,45,...]}`

    依赖：`agent_mcp` 表存在列 `permission_type`/`is_default`；缺列时返回 DDL 建议。

    权限：创建者、同租户管理员（租户非 default）、或具备 write/admin 权限的用户。

    返回：`Result({"agent_id": int, "affected": int, "mode": "EXCLUDE"})` 或缺列错误提示。
    """
    # 排除 MCP 列表；依赖 agent_mcp 表存在 permission_type/is_default 列
    # 请求体：{"mcp_agent_ids": [23,45,...]}
    # 返回：{"agent_id": int, "affected": 插入条数, "mode": "EXCLUDE"} 或缺列错误提示
    tenant_id = require_tenant_id(request)
    user_id = claims.get("sub") if isinstance(claims, dict) else None
    ids: List[int] = []
    for x in (payload or {}).get("mcp_agent_ids", []) or []:
        try:
            ids.append(int(x))
        except Exception:
            continue
    logger.info(
        f"request {request.method} {request.url.path} agent_id={agent_id} tenant_id={tenant_id} user_id={user_id} exclude_ids={ids}"
    )
    res = agent_service.set_agent_mcp_exclude_service(agent_id=agent_id, mcp_agent_ids=ids, tenant_id=tenant_id, claims=claims)
    return Result.ok(res)


@router.delete("/agents/{agent_id}/mcp/reset", response_model=Result)
def reset_agent_mcp(agent_id: int, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    """恢复默认 MCP 配置（清空 agent_mcp 关系，恢复全量可用）。

    参数：
    - `agent_id`: 智能体ID（路径参数）

    权限：创建者、同租户管理员（租户非 default）、或具备 write/admin 权限的用户。

    返回：`Result({"agent_id": int, "affected": int, "mode": "RESET"})`。
    """
    # 恢复默认：清空 agent_mcp 关系，恢复全量可用
    # 返回：{"agent_id": int, "affected": 删除条数, "mode": "RESET"}
    tenant_id = require_tenant_id(request)
    user_id = claims.get("sub") if isinstance(claims, dict) else None
    logger.info(
        f"request {request.method} {request.url.path} agent_id={agent_id} tenant_id={tenant_id} user_id={user_id}"
    )
    res = agent_service.reset_agent_mcp_service(agent_id=agent_id, tenant_id=tenant_id, claims=claims)
    return Result.ok(res)
