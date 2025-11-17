from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from sqlalchemy import text

from agentlz.repositories.db import get_engine


SORT_MAPPING = {
    "id": "id",
    "username": "username",
    "email": "email",
    "fullName": "full_name",
    "role": "role",
    "disabled": "disabled",
    "createdAt": "created_at",
}


def _sanitize_sort(sort_field: str) -> str:
    return SORT_MAPPING.get(sort_field, "id")


def list_users(
    *,
    page: int,
    per_page: int,
    sort: str,
    order: str,
    q: Optional[str],
    tenant_id: str,
    table_name: str,
) -> Tuple[List[Dict[str, Any]], int]:
    """列表查询，返回行与总数"""

    order_dir = "ASC" if order.upper() == "ASC" else "DESC"
    sort_col = _sanitize_sort(sort)
    offset = (page - 1) * per_page

    where = ["tenant_id = :tenant_id"]
    params: Dict[str, Any] = {"tenant_id": tenant_id}
    if q:
        where.append("(username LIKE :q OR email LIKE :q OR full_name LIKE :q)")
        params["q"] = f"%{q}%"
    where_sql = "WHERE " + " AND ".join(where)

    count_sql = text(f"SELECT COUNT(*) AS cnt FROM `{table_name}` {where_sql}")
    list_sql = text(
        f"""
        SELECT id, username, email, full_name, avatar, role, disabled, created_at, created_by_id, tenant_id
        FROM `{table_name}`
        {where_sql}
        ORDER BY {sort_col} {order_dir}
        LIMIT :limit OFFSET :offset
        """
    )

    engine = get_engine()
    with engine.connect() as conn:
        total = conn.execute(count_sql, params).scalar() or 0
        rows = conn.execute(list_sql, {**params, "limit": per_page, "offset": offset}).mappings().all()
    return [dict(r) for r in rows], int(total)


def get_user_by_id(*, user_id: int, tenant_id: str, table_name: str) -> Optional[Dict[str, Any]]:
    sql = text(
        f"""
        SELECT id, username, email, full_name, avatar, role, disabled, created_at, created_by_id, tenant_id
        FROM `{table_name}` WHERE id = :id AND tenant_id = :tenant_id
        """
    )
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(sql, {"id": user_id, "tenant_id": tenant_id}).mappings().first()
    return dict(row) if row else None


def create_user(
    *,
    payload: Dict[str, Any],
    tenant_id: str,
    table_name: str,
) -> Dict[str, Any]:
    """插入用户并返回插入后的记录"""

    now = datetime.utcnow()
    sql = text(
        f"""
        INSERT INTO `{table_name}`
        (username, email, password_hash, full_name, avatar, role, disabled, created_at, created_by_id, tenant_id)
        VALUES (:username, :email, :password_hash, :full_name, :avatar, :role, :disabled, :created_at, :created_by_id, :tenant_id)
        """
    )

    params = {
        "username": payload.get("username"),
        "email": payload.get("email"),
        "password_hash": payload.get("password_hash"),
        "full_name": payload.get("full_name"),
        "avatar": payload.get("avatar"),
        "role": payload.get("role", "user"),
        "disabled": int(bool(payload.get("disabled", False))),
        "created_at": now,
        "created_by_id": payload.get("created_by_id"),
        "tenant_id": tenant_id,
    }

    engine = get_engine()
    with engine.begin() as conn:
        result = conn.execute(sql, params)
        new_id = result.lastrowid
        # 读取并返回插入后的记录
        ret = conn.execute(
            text(
                f"SELECT id, username, email, full_name, avatar, role, disabled, created_at, created_by_id, tenant_id FROM `{table_name}` WHERE id = :id AND tenant_id = :tenant_id"
            ),
            {"id": new_id, "tenant_id": tenant_id},
        ).mappings().first()
        return dict(ret)


def update_user(
    *,
    user_id: int,
    payload: Dict[str, Any],
    tenant_id: str,
    table_name: str,
) -> Optional[Dict[str, Any]]:
    """更新用户，如果不存在返回 None"""

    allowed_cols = [
        "username",
        "email",
        "password_hash",
        "full_name",
        "avatar",
        "role",
        "disabled",
        "created_by_id",
    ]

    sets = []
    params: Dict[str, Any] = {"id": user_id, "tenant_id": tenant_id}
    for col in allowed_cols:
        if col in payload and payload[col] is not None:
            sets.append(f"{col} = :{col}")
            params[col] = payload[col]

    if not sets:
        # 没有任何变更，直接返回当前记录
        return get_user_by_id(user_id=user_id, tenant_id=tenant_id, table_name=table_name)

    sql = text(
        f"UPDATE `{table_name}` SET " + ", ".join(sets) + " WHERE id = :id AND tenant_id = :tenant_id"
    )

    engine = get_engine()
    with engine.begin() as conn:
        result = conn.execute(sql, params)
        if result.rowcount == 0:
            return None
        ret = conn.execute(
            text(
                f"SELECT id, username, email, full_name, avatar, role, disabled, created_at, created_by_id, tenant_id FROM `{table_name}` WHERE id = :id AND tenant_id = :tenant_id"
            ),
            {"id": user_id, "tenant_id": tenant_id},
        ).mappings().first()
        return dict(ret) if ret else None


def delete_user(*, user_id: int, tenant_id: str, table_name: str) -> bool:
    sql = text(f"DELETE FROM `{table_name}` WHERE id = :id AND tenant_id = :tenant_id")
    engine = get_engine()
    with engine.begin() as conn:
        result = conn.execute(sql, {"id": user_id, "tenant_id": tenant_id})
        return result.rowcount > 0