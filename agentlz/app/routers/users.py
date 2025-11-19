from __future__ import annotations
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Request, status, Depends

from agentlz.schemas.user import UserCreate, UserItem, UserUpdate
from agentlz.schemas.responses import Result
from agentlz.services import user_service
from agentlz.app.deps.auth_deps import require_auth, require_tenant_id, require_admin, require_admin_or_self
# 注：以上依赖用于从请求中解析租户与用户身份（JWT claims），并进行权限校验。

"""用户路由（CRUD + 列表）

路由前缀 /v1，所有操作需校验租户头。

权限约定：除对“本人”的查询/修改之外，均需管理员身份；
本人例外的判定依据为 JWT 的 `sub` 与目标 `user_id` 相同。
"""
router = APIRouter(prefix="/v1", tags=["users"])


@router.get("/users", response_model=Result)
def list_users(
    request: Request,
    _page: int = Query(1, ge=1),
    _perPage: int = Query(10, ge=1, le=100),
    _sort: str = Query("id"),
    _order: str = Query("ASC"),
    q: Optional[str] = Query(None),
    claims: Dict[str, Any] = Depends(require_auth),
):
    # 仅管理员可访问列表；claims 由 require_auth 注入，包含当前登录用户信息（sub 等）。
    tenant_id = require_tenant_id(request)
    require_admin(claims, tenant_id)
    rows, total = user_service.list_users_service(
        page=_page, per_page=_perPage, sort=_sort, order=_order, q=q, tenant_id=tenant_id
    )
    data_items = [UserItem(**r) for r in rows]
    # 统一返回结构：Result，真实数据置于 data 字段
    return Result.ok({"data": data_items, "total": total})


@router.get("/users/{user_id}", response_model=Result)
def get_user(user_id: int, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    # 管理员或本人（JWT sub == user_id）可访问详情
    tenant_id = require_tenant_id(request)
    require_admin_or_self(user_id, claims, tenant_id)
    row = user_service.get_user_service(user_id=user_id, tenant_id=tenant_id)
    if not row:
        raise HTTPException(status_code=404, detail="用户不存在")
    return Result.ok(row)


@router.post("/users", response_model=Result, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    # 仅管理员可创建用户
    tenant_id = require_tenant_id(request)
    require_admin(claims, tenant_id)
    row = user_service.create_user_service(payload=payload, tenant_id=tenant_id)
    return Result.ok(row)


@router.put("/users/{user_id}", response_model=Result)
def update_user(user_id: int, payload: UserUpdate, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    # 管理员或本人可更新
    tenant_id = require_tenant_id(request)
    require_admin_or_self(user_id, claims, tenant_id)
    row = user_service.update_user_service(user_id=user_id, payload=payload, tenant_id=tenant_id)
    if not row:
        raise HTTPException(status_code=404, detail="用户不存在")
    return Result.ok(row)


@router.delete("/users/{user_id}", response_model=Result)
def delete_user(user_id: int, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    # 仅管理员可删除用户
    tenant_id = require_tenant_id(request)
    require_admin(claims, tenant_id)
    ok = user_service.delete_user_service(user_id=user_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=404, detail="用户不存在")
    return Result.ok({})