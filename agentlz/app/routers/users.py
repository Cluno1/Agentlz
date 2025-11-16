from __future__ import annotations

"""用户路由（CRUD + 列表）

路由前缀 /v1，所有操作需校验租户头。
"""

from typing import Optional, Dict

from fastapi import APIRouter, HTTPException, Query, Request, status

from agentlz.config.settings import get_settings
from agentlz.schemas.user import ListResponse, UserCreate, UserItem, UserUpdate
from agentlz.services import user_service


router = APIRouter(prefix="/v1", tags=["users"])


def _require_tenant_id(request: Request) -> str:
    s = get_settings()
    tenant_header = getattr(s, "tenant_id_header", "X-Tenant-ID")
    tenant_id = request.headers.get(tenant_header)
    if not tenant_id:
        raise HTTPException(status_code=400, detail=f"Missing tenant header: {tenant_header}")
    return tenant_id


@router.get("/users", response_model=ListResponse)
def list_users(
    request: Request,
    _page: int = Query(1, ge=1),
    _perPage: int = Query(10, ge=1, le=100),
    _sort: str = Query("id"),
    _order: str = Query("ASC"),
    q: Optional[str] = Query(None),
):
    tenant_id = _require_tenant_id(request)
    rows, total = user_service.list_users_service(
        page=_page, per_page=_perPage, sort=_sort, order=_order, q=q, tenant_id=tenant_id
    )
    # Pydantic 会进行模型转换
    data = [UserItem(**r) for r in rows]
    return {"data": data, "total": total}


@router.get("/users/{user_id}", response_model=UserItem)
def get_user(user_id: int, request: Request):
    tenant_id = _require_tenant_id(request)
    row = user_service.get_user_service(user_id=user_id, tenant_id=tenant_id)
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return UserItem(**row)


@router.post("/users", response_model=UserItem, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, request: Request):
    tenant_id = _require_tenant_id(request)
    row = user_service.create_user_service(payload=payload, tenant_id=tenant_id)
    return UserItem(**row)


@router.put("/users/{user_id}", response_model=UserItem)
def update_user(user_id: int, payload: UserUpdate, request: Request):
    tenant_id = _require_tenant_id(request)
    row = user_service.update_user_service(user_id=user_id, payload=payload, tenant_id=tenant_id)
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return UserItem(**row)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, request: Request):
    tenant_id = _require_tenant_id(request)
    ok = user_service.delete_user_service(user_id=user_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found")
    return {}