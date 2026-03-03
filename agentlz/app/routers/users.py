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


def _current_user_from_claims(claims: Dict[str, Any], tenant_id: str) -> Optional[Dict[str, Any]]:
    try:
        uid = int(str(claims.get("sub")))
    except Exception:
        return None
    return user_service.get_user_service(user_id=uid, tenant_id=tenant_id)


def _is_super_admin(claims: Dict[str, Any], tenant_id: str) -> bool:
    user = _current_user_from_claims(claims, tenant_id)
    if not user:
        return False
    return (
        str(user.get("role") or "") == "admin"
        and str(user.get("tenant_id") or "") in {"system", "default"}
    )


@router.get("/users", response_model=Result)
def list_users(
    request: Request,
    page: int = Query(1, ge=1),
    perPage: int = Query(10, ge=1, le=100),
    sort: str = Query("id"),
    order: str = Query("ASC"),
    q: Optional[str] = Query(None),
    claims: Dict[str, Any] = Depends(require_auth),
):
    # 仅管理员可访问列表；claims 由 require_auth 注入，包含当前登录用户信息（sub 等）。
    tenant_id = require_tenant_id(request)
    require_admin(claims, tenant_id)
    if _is_super_admin(claims, tenant_id):
        rows, total = user_service.list_users_service(
            page=page, per_page=perPage, sort=sort, order=order, q=q, tenant_id=None
        )
    else:
        rows, total = user_service.list_users_service(
            page=page, per_page=perPage, sort=sort, order=order, q=q, tenant_id=tenant_id
        )
    data_items = [UserItem(**r) for r in rows]
    # 统一返回结构：Result，真实数据置于 data 字段
    return Result.ok({"data": data_items, "total": total})


@router.get("/users/{user_id}", response_model=Result)
def get_user(user_id: int, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    # 管理员或本人（JWT sub == user_id）可访问详情
    tenant_id = require_tenant_id(request)
    require_admin_or_self(user_id, claims, tenant_id)
    if _is_super_admin(claims, tenant_id):
        row = user_service.get_user_any_service(user_id=user_id)
    else:
        row = user_service.get_user_service(user_id=user_id, tenant_id=tenant_id)
    if not row:
        raise HTTPException(status_code=404, detail="用户不存在")
    return Result.ok(row)


@router.post("/users", response_model=Result, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    # 仅管理员可创建用户
    tenant_id = require_tenant_id(request)
    require_admin(claims, tenant_id)
    target_tenant_id = tenant_id
    if _is_super_admin(claims, tenant_id) and payload.tenant_id:
        target_tenant_id = payload.tenant_id
    row = user_service.create_user_service(payload=payload, tenant_id=target_tenant_id)
    return Result.ok(row)


@router.put("/users/{user_id}", response_model=Result)
def update_user(user_id: int, payload: UserUpdate, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    # 管理员或本人可更新
    tenant_id = require_tenant_id(request)
    require_admin_or_self(user_id, claims, tenant_id)
    is_self = str(user_id) == str(claims.get("sub"))
    current_user = None
    try:
        current_user_id = int(str(claims.get("sub")))
        current_user = user_service.get_user_service(user_id=current_user_id, tenant_id=tenant_id)
    except Exception:
        current_user = None
    is_admin = bool(current_user and current_user.get("role") == "admin")
    if payload.new_password is not None:
        if is_self:
            stored = user_service.get_password_hash_service(user_id=user_id, tenant_id=tenant_id) or ""
            provided = str(payload.current_password or "")
            if str(stored) != provided:
                raise HTTPException(status_code=400, detail="当前密码错误")
        payload.password = payload.new_password
    if payload.tenant_id is not None and not _is_super_admin(claims, tenant_id):
        raise HTTPException(status_code=403, detail="无权限修改租户归属")
    if _is_super_admin(claims, tenant_id) and not is_self:
        target = user_service.get_user_any_service(user_id=user_id)
        if not target:
            raise HTTPException(status_code=404, detail="用户不存在")
        row = user_service.update_user_service(
            user_id=user_id, payload=payload, tenant_id=str(target.get("tenant_id") or "")
        )
    else:
        row = user_service.update_user_service(user_id=user_id, payload=payload, tenant_id=tenant_id)
    if not row:
        raise HTTPException(status_code=404, detail="用户不存在")
    return Result.ok(row)


@router.delete("/users/{user_id}", response_model=Result)
def delete_user(user_id: int, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    # 仅管理员可删除用户
    tenant_id = require_tenant_id(request)
    require_admin(claims, tenant_id)
    if _is_super_admin(claims, tenant_id):
        target = user_service.get_user_any_service(user_id=user_id)
        if not target:
            raise HTTPException(status_code=404, detail="用户不存在")
        ok = user_service.delete_user_service(
            user_id=user_id, tenant_id=str(target.get("tenant_id") or "")
        )
    else:
        ok = user_service.delete_user_service(user_id=user_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=404, detail="用户不存在")
    return Result.ok({})
