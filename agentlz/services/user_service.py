from __future__ import annotations

"""用户服务层

封装业务逻辑：参数整合、租户校验、密码到 password_hash 字段的转换等。
"""

from typing import Any, Dict, Optional, Tuple

from agentlz.config.settings import get_settings
from agentlz.repositories import user_repository as repo
from agentlz.schemas.user import UserCreate, UserUpdate


def _get_table_and_header() -> Tuple[str, str]:
    s = get_settings()
    table_name = getattr(s, "user_table_name", "users")
    tenant_header = getattr(s, "tenant_id_header", "X-Tenant-ID")
    return table_name, tenant_header


def list_users_service(
    *, page: int, per_page: int, sort: str, order: str, q: Optional[str], tenant_id: str
):
    table_name, _ = _get_table_and_header()
    rows, total = repo.list_users(
        page=page,
        per_page=per_page,
        sort=sort,
        order=order,
        q=q,
        tenant_id=tenant_id,
        table_name=table_name,
    )
    # 统一把 created_at 转成字符串以简化前端展示
    for r in rows:
        if r.get("created_at") is not None:
            r["created_at"] = str(r["created_at"])  # ISO 格式化可在后续完善
    return rows, total


def get_user_service(*, user_id: int, tenant_id: str) -> Optional[Dict[str, Any]]:
    table_name, _ = _get_table_and_header()
    row = repo.get_user_by_id(user_id=user_id, tenant_id=tenant_id, table_name=table_name)
    if row and row.get("created_at") is not None:
        row["created_at"] = str(row["created_at"])
    return row


def create_user_service(*, payload: UserCreate, tenant_id: str) -> Dict[str, Any]:
    table_name, _ = _get_table_and_header()
    # 将明文 password 写入 password_hash 列（后续可替换为哈希）
    data = {
        "username": payload.username,
        "email": payload.email,
        "password_hash": payload.password,  # TODO: 上线前改为哈希
        "full_name": payload.full_name,
        "avatar": payload.avatar,
        "role": payload.role or "user",
        "disabled": payload.disabled or False,
        "created_by_id": payload.created_by_id,
    }
    row = repo.create_user(payload=data, tenant_id=tenant_id, table_name=table_name)
    if row.get("created_at") is not None:
        row["created_at"] = str(row["created_at"])
    return row


def update_user_service(*, user_id: int, payload: UserUpdate, tenant_id: str) -> Optional[Dict[str, Any]]:
    table_name, _ = _get_table_and_header()
    data: Dict[str, Any] = {}
    if payload.username is not None:
        data["username"] = payload.username
    if payload.email is not None:
        data["email"] = payload.email
    if payload.password is not None:
        data["password_hash"] = payload.password
    if payload.full_name is not None:
        data["full_name"] = payload.full_name
    if payload.avatar is not None:
        data["avatar"] = payload.avatar
    if payload.role is not None:
        data["role"] = payload.role
    if payload.disabled is not None:
        data["disabled"] = int(bool(payload.disabled))
    if payload.created_by_id is not None:
        data["created_by_id"] = payload.created_by_id

    row = repo.update_user(user_id=user_id, payload=data, tenant_id=tenant_id, table_name=table_name)
    if row and row.get("created_at") is not None:
        row["created_at"] = str(row["created_at"])
    return row


def delete_user_service(*, user_id: int, tenant_id: str) -> bool:
    table_name, _ = _get_table_and_header()
    return repo.delete_user(user_id=user_id, tenant_id=tenant_id, table_name=table_name)