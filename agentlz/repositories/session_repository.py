from __future__ import annotations

"""会话仓储（MySQL）

职责
- 仅负责读取指定记录（record_id）下的会话原始数据
- 保持 SQL 与数据访问纯净，不做裁剪/解析（服务层负责）

实现说明
- 所有 SQL 使用参数化（sqlalchemy.text）
"""

from typing import Any, Dict, List, Tuple, Optional
from sqlalchemy import text

from agentlz.core.database import get_mysql_engine
from datetime import datetime, timezone, timedelta
import json


def list_sessions_by_record(*, record_id: int, table_name: str) -> List[Dict[str, Any]]:
    """按对话轮次输出会话原始数据（升序）

    入参
    - record_id: 记录ID
    - table_name: 会话表名

    返回
    - 列表：每项包含 id, count, meta_input, meta_output, zip, created_at
    """
    sql = text(
        f"""
        SELECT id, count, meta_input, meta_output, zip, created_at
        FROM `{table_name}`
        WHERE record_id = :rid
        ORDER BY count ASC, id ASC
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        rows = conn.execute(sql, {"rid": int(record_id)}).mappings().all()
    return [dict(r) for r in rows]


def create_session(*, record_id: int, count: int, meta_input: Any, meta_output: Any, zip: str | None, table_name: str) -> Dict[str, Any]:
    mi = meta_input if isinstance(meta_input, str) else json.dumps(meta_input, ensure_ascii=False)
    mo = meta_output if isinstance(meta_output, str) else json.dumps(meta_output, ensure_ascii=False)
    now = datetime.now(timezone(timedelta(hours=8)))
    sql = text(
        f"""
        INSERT INTO `{table_name}`
        (record_id, count, meta_input, meta_output, zip, created_at)
        VALUES (:rid, :cnt, :mi, :mo, :zip, :created_at)
        """
    )
    engine = get_mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(sql, {"rid": int(record_id), "cnt": int(count), "mi": mi, "mo": mo, "zip": zip or "", "created_at": now})
        new_id = result.lastrowid
        ret = conn.execute(
            text(
                f"SELECT id, count, meta_input, meta_output, zip, created_at FROM `{table_name}` WHERE id = :id"
            ),
            {"id": new_id},
        ).mappings().first()
    return dict(ret) if ret else {}


# 排序字段白名单（外部字段 -> 数据库列名）
SORT_MAPPING = {
    "id": "id",
    "count": "count",
    "createdAt": "created_at",
}


def _sanitize_sort(sort_field: str) -> str:
    return SORT_MAPPING.get(str(sort_field or ""), "created_at")


def list_sessions_by_record_paginated(
    *,
    record_id: int,
    page: int,
    per_page: int,
    sort: str = "createdAt",
    order: str = "DESC",
    table_name: str,
) -> Tuple[List[Dict[str, Any]], int]:
    """分页查询指定记录的会话列表（默认按创建时间倒序）

    返回 (rows, total)，`rows` 每行包含：id, count, meta_input, meta_output, zip, created_at
    """
    order_dir = "ASC" if str(order or "").upper() == "ASC" else "DESC"
    sort_col = _sanitize_sort(sort)
    offset = (max(1, int(page)) - 1) * max(1, int(per_page))

    count_sql = text(
        f"SELECT COUNT(*) AS cnt FROM `{table_name}` WHERE record_id = :rid"
    )
    list_sql = text(
        f"""
        SELECT id, count, meta_input, meta_output, zip, created_at
        FROM `{table_name}`
        WHERE record_id = :rid
        ORDER BY {sort_col} {order_dir}, id DESC
        LIMIT :limit OFFSET :offset
        """
    )

    engine = get_mysql_engine()
    with engine.connect() as conn:
        total = conn.execute(count_sql, {"rid": int(record_id)}).scalar() or 0
        rows = conn.execute(list_sql, {"rid": int(record_id), "limit": per_page, "offset": offset}).mappings().all()
    return [dict(r) for r in rows], int(total)

