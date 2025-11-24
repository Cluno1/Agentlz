from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy import text

from agentlz.core.database import get_mysql_engine


# 排序字段白名单映射（外部字段名 -> 数据库列名）
SORT_MAPPING = {
    "id": "id",
    "userId": "user_id",
    "docId": "doc_id",
    "perm": "perm",
    "createdAt": "created_at",
}


def _sanitize_sort(sort_field: str) -> str:
    # 过滤排序字段，默认为 id
    return SORT_MAPPING.get(sort_field, "id")


def list_user_doc_perms(
    *,
    page: int,
    per_page: int,
    sort: str,
    order: str,
    q: Optional[str],
    user_id: Optional[int],
    doc_id: Optional[str],
    table_name: str,
) -> Tuple[List[Dict[str, Any]], int]:
    # 分页查询用户-文档权限关系，支持按 user_id / doc_id 过滤与 doc_id 模糊搜索
    """列表查询，返回行与总数"""

    order_dir = "ASC" if order.upper() == "ASC" else "DESC"
    sort_col = _sanitize_sort(sort)
    offset = (page - 1) * per_page

    where: List[str] = []
    params: Dict[str, Any] = {}
    if user_id is not None:
        where.append("user_id = :user_id")
        params["user_id"] = user_id
    if doc_id is not None:
        where.append("doc_id = :doc_id")
        params["doc_id"] = doc_id
    if q:
        # 仅对 doc_id 做模糊匹配；perm 为枚举不适合 LIKE
        where.append("doc_id LIKE :q")
        params["q"] = f"%{q}%"
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    count_sql = text(f"SELECT COUNT(*) AS cnt FROM `{table_name}` {where_sql}")
    list_sql = text(
        f"""
        SELECT id, user_id, doc_id, perm, created_at
        FROM `{table_name}`
        {where_sql}
        ORDER BY {sort_col} {order_dir}
        LIMIT :limit OFFSET :offset
        """
    )

    engine = get_mysql_engine()
    with engine.connect() as conn:
        total = conn.execute(count_sql, params).scalar() or 0
        rows = conn.execute(list_sql, {**params, "limit": per_page, "offset": offset}).mappings().all()
    return [dict(r) for r in rows], int(total)


def get_perm_by_id(*, perm_id: int, table_name: str) -> Optional[Dict[str, Any]]:
    # 按主键ID查询权限记录
    sql = text(
        f"""
        SELECT id, user_id, doc_id, perm, created_at
        FROM `{table_name}` WHERE id = :id
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        row = conn.execute(sql, {"id": perm_id}).mappings().first()
    return dict(row) if row else None


def get_perm_by_user_doc(*, user_id: int, doc_id: str, table_name: str) -> Optional[Dict[str, Any]]:
    # 按唯一键 (user_id, doc_id) 查询权限记录
    sql = text(
        f"""
        SELECT id, user_id, doc_id, perm, created_at
        FROM `{table_name}` WHERE user_id = :user_id AND doc_id = :doc_id
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        row = conn.execute(sql, {"user_id": user_id, "doc_id": doc_id}).mappings().first()
    return dict(row) if row else None


def create_user_doc_perm(
    *,
    payload: Dict[str, Any],
    table_name: str,
) -> Dict[str, Any]:
    # 创建用户文档权限关系并返回记录
    """插入权限记录并返回插入后的记录"""

    now = datetime.now(timezone.utc)
    sql = text(
        f"""
        INSERT INTO `{table_name}`
        (user_id, doc_id, perm, created_at)
        VALUES (:user_id, :doc_id, :perm, :created_at)
        """
    )

    params = {
        "user_id": payload.get("user_id"),
        "doc_id": payload.get("doc_id"),
        "perm": payload.get("perm", "read"),
        "created_at": now,
    }

    engine = get_mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(sql, params)
        new_id = result.lastrowid
        # 读取并返回插入后的记录
        ret = conn.execute(
            text(
                f"SELECT id, user_id, doc_id, perm, created_at FROM `{table_name}` WHERE id = :id"
            ),
            {"id": new_id},
        ).mappings().first()
        return dict(ret)


def update_user_doc_perm(
    *,
    perm_id: int,
    payload: Dict[str, Any],
    table_name: str,
) -> Optional[Dict[str, Any]]:
    # 更新权限（仅允许修改 perm 字段）
    """更新权限记录，如果不存在返回 None"""

    allowed_cols = ["perm"]

    sets = []
    params: Dict[str, Any] = {"id": perm_id}
    for col in allowed_cols:
        if col in payload and payload[col] is not None:
            sets.append(f"{col} = :{col}")
            params[col] = payload[col]

    if not sets:
        # 没有任何变更，直接返回当前记录
        return get_perm_by_id(perm_id=perm_id, table_name=table_name)

    sql = text(f"UPDATE `{table_name}` SET " + ", ".join(sets) + " WHERE id = :id")
    engine = get_mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(sql, params)
        if result.rowcount == 0:
            return None
        ret = conn.execute(
            text(
                f"SELECT id, user_id, doc_id, perm, created_at FROM `{table_name}` WHERE id = :id"
            ),
            {"id": perm_id},
        ).mappings().first()
        return dict(ret) if ret else None


def delete_user_doc_perm(*, perm_id: int, table_name: str) -> bool:
    # 删除权限记录（按主键）
    sql = text(f"DELETE FROM `{table_name}` WHERE id = :id")
    engine = get_mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(sql, {"id": perm_id})
        return result.rowcount > 0


def delete_user_doc_perm_by_pair(*, user_id: int, doc_id: str, table_name: str) -> bool:
    # 删除权限记录（按唯一键 user_id + doc_id）
    sql = text(f"DELETE FROM `{table_name}` WHERE user_id = :user_id AND doc_id = :doc_id")
    engine = get_mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(sql, {"user_id": user_id, "doc_id": doc_id})
        return result.rowcount > 0