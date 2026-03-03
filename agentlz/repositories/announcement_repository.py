from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import text
from agentlz.core.database import get_mysql_engine

SORT_MAPPING = {
    "id": "id",
    "title": "title",
    "created_at": "created_at",
    "updated_at": "updated_at",
}


def _sanitize_sort(sort_field: str) -> str:
    return SORT_MAPPING.get(sort_field, "id")


def list_announcements(
    *,
    page: int,
    per_page: int,
    sort: str,
    order: str,
    q: Optional[str],
    tenant_id: str,
    table_name: str,
) -> Tuple[List[Dict[str, Any]], int]:
    order_dir = "ASC" if str(order or "").upper() == "ASC" else "DESC"
    sort_col = _sanitize_sort(sort)
    offset = (max(1, int(page)) - 1) * max(1, int(per_page))
    where = ["tenant_id = :tenant_id"]
    params: Dict[str, Any] = {"tenant_id": tenant_id}
    if q:
        where.append("(title LIKE :q OR content LIKE :q)")
        params["q"] = f"%{q}%"
    where_sql = "WHERE " + " AND ".join(where)
    count_sql = text(f"SELECT COUNT(*) AS cnt FROM `{table_name}` {where_sql}")
    list_sql = text(
        f"""
        SELECT id, tenant_id, title, content, disabled, created_at, created_by_id, updated_at, updated_by_id
        FROM `{table_name}`
        {where_sql}
        ORDER BY {sort_col} {order_dir}
        LIMIT :limit OFFSET :offset
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        total = conn.execute(count_sql, params).scalar() or 0
        rows = conn.execute(
            list_sql, {**params, "limit": per_page, "offset": offset}
        ).mappings().all()
    return [dict(r) for r in rows], int(total)


def list_visible_announcements(
    *,
    tenant_id: str,
    limit: int,
    table_name: str,
) -> List[Dict[str, Any]]:
    sql = text(
        f"""
        SELECT id, tenant_id, title, content, disabled, created_at, created_by_id, updated_at, updated_by_id
        FROM `{table_name}`
        WHERE disabled = 0 AND (tenant_id = 'system' OR tenant_id = :tenant_id)
        ORDER BY created_at DESC
        LIMIT :limit
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        rows = conn.execute(sql, {"tenant_id": tenant_id, "limit": limit}).mappings().all()
    return [dict(r) for r in rows]


def get_announcement_by_id(
    *,
    announcement_id: int,
    table_name: str,
) -> Optional[Dict[str, Any]]:
    sql = text(
        f"""
        SELECT id, tenant_id, title, content, disabled, created_at, created_by_id, updated_at, updated_by_id
        FROM `{table_name}` WHERE id = :id
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        row = conn.execute(sql, {"id": int(announcement_id)}).mappings().first()
    return dict(row) if row else None


def create_announcement(
    *,
    payload: Dict[str, Any],
    table_name: str,
) -> Dict[str, Any]:
    sql = text(
        f"""
        INSERT INTO `{table_name}` (tenant_id, title, content, disabled, created_by_id, updated_by_id)
        VALUES (:tenant_id, :title, :content, :disabled, :created_by_id, :updated_by_id)
        """
    )
    params = {
        "tenant_id": payload.get("tenant_id"),
        "title": payload.get("title"),
        "content": payload.get("content"),
        "disabled": 1 if payload.get("disabled") else 0,
        "created_by_id": payload.get("created_by_id"),
        "updated_by_id": payload.get("updated_by_id"),
    }
    engine = get_mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(sql, params)
        new_id = result.lastrowid
        ret = conn.execute(
            text(
                f"SELECT id, tenant_id, title, content, disabled, created_at, created_by_id, updated_at, updated_by_id FROM `{table_name}` WHERE id = :id"
            ),
            {"id": new_id},
        ).mappings().first()
        return dict(ret)


def update_announcement(
    *,
    announcement_id: int,
    payload: Dict[str, Any],
    table_name: str,
) -> Optional[Dict[str, Any]]:
    allowed_cols = ["title", "content", "disabled", "updated_by_id"]
    sets: List[str] = []
    params: Dict[str, Any] = {"id": int(announcement_id)}
    for col in allowed_cols:
        if col in payload and payload[col] is not None:
            val = payload[col]
            if col == "disabled":
                val = 1 if bool(val) else 0
            sets.append(f"{col} = :{col}")
            params[col] = val
    if not sets:
        return get_announcement_by_id(announcement_id=announcement_id, table_name=table_name)
    sql = text(f"UPDATE `{table_name}` SET " + ", ".join(sets) + " WHERE id = :id")
    engine = get_mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(sql, params)
        if result.rowcount == 0:
            return None
        ret = conn.execute(
            text(
                f"SELECT id, tenant_id, title, content, disabled, created_at, created_by_id, updated_at, updated_by_id FROM `{table_name}` WHERE id = :id"
            ),
            {"id": int(announcement_id)},
        ).mappings().first()
        return dict(ret) if ret else None


def delete_announcement(
    *,
    announcement_id: int,
    table_name: str,
) -> bool:
    sql = text(f"DELETE FROM `{table_name}` WHERE id = :id")
    engine = get_mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(sql, {"id": int(announcement_id)})
        return result.rowcount > 0
