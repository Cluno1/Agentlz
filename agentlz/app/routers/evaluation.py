from __future__ import annotations
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from agentlz.app.deps.auth_deps import require_auth, require_tenant_id
from agentlz.schemas.responses import Result
from agentlz.schemas.evaluation import (
    EvaluationDatasetCreateRequest,
    EvaluationParseAlpacaRequest,
    EvaluationStartRequest,
)
from agentlz.services import evaluation_service

router = APIRouter(prefix="/v1/evaluation", tags=["evaluation"])


@router.get("/datasets", response_model=Result)
def list_evaluation_datasets(
    request: Request,
    claims: Dict[str, Any] = Depends(require_auth),
    page: int = Query(1, ge=1, description="页码，从1开始"),
    per_page: int = Query(10, ge=1, le=200, description="每页条数"),
    sort: str = Query("id", description="排序字段"),
    order: str = Query("DESC", regex="^(ASC|DESC)$", description="排序方向"),
    q: Optional[str] = Query(None, description="标题/文件名搜索"),
    type: str = Query("tenant", description="数据范围：self/tenant/system"),
):
    """
    查询测评数据集分页列表。

    参数：
    - page/per_page/sort/order/q：分页与检索参数。
    - type：数据范围，支持 self/tenant/system。
    - request/claims：用于鉴权和租户解析。

    返回：
    - Result.data = {rows, total}。
    """
    tenant_id = require_tenant_id(request)
    rows, total = evaluation_service.list_evaluation_datasets_service(
        page=page,
        per_page=per_page,
        sort=sort,
        order=order,
        q=q,
        type=type,
        tenant_id=tenant_id,
        claims=claims,
    )
    return Result.ok(data={"rows": rows, "total": total})


@router.post("/datasets", response_model=Result)
def create_evaluation_dataset(
    payload: EvaluationDatasetCreateRequest,
    request: Request,
    claims: Dict[str, Any] = Depends(require_auth),
):
    """
    创建测评数据集。

    参数：
    - payload：测评集创建参数（name/type/status/data_json）。
    - request/claims：用于租户与身份校验。

    返回：
    - Result.data = 新建数据集记录。
    """
    tenant_id = require_tenant_id(request)
    row = evaluation_service.create_evaluation_dataset_service(
        name=payload.name,
        type=payload.type,
        status=payload.status,
        data_json=payload.data_json,
        tenant_id=tenant_id,
        claims=claims,
    )
    return Result.ok(data=row)


@router.get("/datasets/{dataset_id}", response_model=Result)
def get_evaluation_dataset(
    dataset_id: str,
    request: Request,
    claims: Dict[str, Any] = Depends(require_auth),
    type: str = Query("tenant", description="数据范围：self/tenant/system"),
):
    """
    查询测评数据集详情。

    参数：
    - dataset_id：测评集ID。
    - type：数据范围，支持 self/tenant/system。
    - request/claims：用于鉴权与租户解析。

    返回：
    - Result.data = 数据集详情。
    """
    tenant_id = require_tenant_id(request)
    row = evaluation_service.get_evaluation_dataset_service(
        dataset_id=dataset_id,
        type=type,
        tenant_id=tenant_id,
        claims=claims,
    )
    if not row:
        raise HTTPException(status_code=404, detail="测评集不存在")
    return Result.ok(data=row)


@router.delete("/datasets/{dataset_id}", response_model=Result)
def delete_evaluation_dataset(
    dataset_id: str,
    request: Request,
    claims: Dict[str, Any] = Depends(require_auth),
    type: str = Query("tenant", description="数据范围：self/tenant/system"),
):
    """
    删除测评数据集。

    参数：
    - dataset_id：测评集ID。
    - type：数据范围，支持 self/tenant/system。
    - request/claims：用于鉴权与租户解析。

    返回：
    - Result.data = {}。
    """
    tenant_id = require_tenant_id(request)
    ok = evaluation_service.delete_evaluation_dataset_service(
        dataset_id=dataset_id,
        type=type,
        tenant_id=tenant_id,
        claims=claims,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="测评集不存在")
    return Result.ok(data={})


@router.post("/datasets/parse-alpaca", response_model=Result)
def parse_dataset_to_alpaca(
    payload: EvaluationParseAlpacaRequest,
    request: Request,
    claims: Dict[str, Any] = Depends(require_auth),
):
    """
    占位接口：将任意 JSON 数据转换为 alpaca 格式。

    参数：
    - payload：{raw_json, hint}。
    - request/claims：用于鉴权与租户上下文保持一致。

    返回：
    - Result.data = {is_alpaca, items, hint}。
    """
    tenant_id = require_tenant_id(request)
    data = evaluation_service.parse_alpaca_placeholder_service(
        raw_json=payload.raw_json,
        hint=payload.hint,
        claims=claims,
    )
    return Result.ok(data={**data, "tenant_id": tenant_id})


@router.post("/start", response_model=Result)
def start_evaluation(payload: EvaluationStartRequest, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    """
    启动测评任务并投递 MQ。

    参数：
    - payload：{eva_json_id, agent_id, type?}。
    - request/claims：用于权限校验与租户解析。

    返回：
    - Result.data = {status, eva_content_id, eva_version_id}。
    """
    tenant_id = require_tenant_id(request)
    data = evaluation_service.start_evaluation_service(
        eva_json_id=payload.eva_json_id,
        agent_id=payload.agent_id,
        type=payload.type,
        tenant_id=tenant_id,
        claims=claims,
    )
    return Result.ok(data=data)


@router.get("/agents/{agent_id:int}/versions", response_model=Result)
def list_agent_versions(
    agent_id: int,
    request: Request,
    claims: Dict[str, Any] = Depends(require_auth),
    page: int = Query(1, ge=1, description="页码，从1开始"),
    per_page: int = Query(10, ge=1, le=200, description="每页条数"),
    sort: str = Query("id", description="排序字段"),
    order: str = Query("DESC", regex="^(ASC|DESC)$", description="排序方向"),
):
    """
    查询指定 Agent 的测评版本列表。

    参数：
    - agent_id：Agent ID。
    - page/per_page/sort/order：分页排序参数。
    - request/claims：用于鉴权与租户解析。

    返回：
    - Result.data = {rows, total}。
    """
    tenant_id = require_tenant_id(request)
    rows, total = evaluation_service.list_agent_versions_service(
        agent_id=agent_id,
        tenant_id=tenant_id,
        page=page,
        per_page=per_page,
        sort=sort,
        order=order,
        claims=claims,
    )
    return Result.ok(data={"rows": rows, "total": total})


@router.get("/agents/{agent_id:int}/contents", response_model=Result)
def list_agent_contents(
    agent_id: int,
    request: Request,
    claims: Dict[str, Any] = Depends(require_auth),
    eva_version_id: Optional[int] = Query(None, description="按版本过滤"),
    page: int = Query(1, ge=1, description="页码，从1开始"),
    per_page: int = Query(10, ge=1, le=200, description="每页条数"),
    sort: str = Query("id", description="排序字段"),
    order: str = Query("DESC", regex="^(ASC|DESC)$", description="排序方向"),
):
    """
    查询指定 Agent 的测评结果历史。

    参数：
    - agent_id：Agent ID。
    - eva_version_id：可选版本过滤。
    - page/per_page/sort/order：分页排序参数。
    - request/claims：用于鉴权与租户解析。

    返回：
    - Result.data = {rows, total}。
    """
    tenant_id = require_tenant_id(request)
    rows, total = evaluation_service.list_agent_contents_service(
        agent_id=agent_id,
        eva_version_id=eva_version_id,
        tenant_id=tenant_id,
        page=page,
        per_page=per_page,
        sort=sort,
        order=order,
        claims=claims,
    )
    return Result.ok(data={"rows": rows, "total": total})


@router.get("/contents/{content_id:int}", response_model=Result)
def get_content_detail(
    content_id: int,
    request: Request,
    claims: Dict[str, Any] = Depends(require_auth),
):
    """
    查询单次测评结果详情。

    参数：
    - content_id：测评结果ID。
    - request/claims：用于鉴权与租户解析。

    返回：
    - Result.data = 测评详情。
    """
    tenant_id = require_tenant_id(request)
    row = evaluation_service.get_content_detail_service(content_id=content_id, tenant_id=tenant_id, claims=claims)
    if not row:
        raise HTTPException(status_code=404, detail="测评结果不存在")
    return Result.ok(data=row)
