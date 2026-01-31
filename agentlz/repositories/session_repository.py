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
        SELECT id, record_id, count, meta_input, meta_output, zip, request_id, zip_status, zip_updated_at, created_at
        FROM `{table_name}`
        WHERE record_id = :rid
        ORDER BY count ASC, id ASC
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        rows = conn.execute(sql, {"rid": int(record_id)}).mappings().all()
    return [dict(r) for r in rows]


def get_last_count(*, record_id: int, table_name: str) -> int:
    """获取某个 record_id 当前最大的轮次 count（不存在则返回 0）。"""
    sql = text(
        f"SELECT COALESCE(MAX(count), 0) AS max_count FROM `{table_name}` WHERE record_id = :rid"
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        v = conn.execute(sql, {"rid": int(record_id)}).scalar()
    try:
        return int(v or 0)
    except Exception:
        return 0


def list_last_sessions(*, record_id: int, limit: int = 50, table_name: str) -> List[Dict[str, Any]]:
    """读取某个 record_id 最近 N 条会话（按旧→新顺序返回）。"""
    sql = text(
        f"""
        SELECT id, record_id, count, meta_input, meta_output, zip, request_id, zip_status, zip_updated_at, created_at
        FROM `{table_name}`
        WHERE record_id = :rid
        ORDER BY count DESC, id DESC
        LIMIT :limit
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        rows = conn.execute(sql, {"rid": int(record_id), "limit": int(limit)}).mappings().all()
    out = [dict(r) for r in rows]
    out.reverse()
    return out


def get_session_by_id(*, session_id: int, table_name: str) -> Optional[Dict[str, Any]]:
    """按主键 id 查询单条 session。"""
    sql = text(
        f"""
        SELECT id, record_id, count, meta_input, meta_output, zip, request_id, zip_status, zip_updated_at, created_at
        FROM `{table_name}`
        WHERE id = :id
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        row = conn.execute(sql, {"id": int(session_id)}).mappings().first()
    return dict(row) if row else None


def get_session_by_request_id(*, request_id: str, table_name: str) -> Optional[Dict[str, Any]]:
    """按 request_id 查询单条 session（用于幂等）。"""
    sql = text(
        f"""
        SELECT id, record_id, count, meta_input, meta_output, zip, request_id, zip_status, zip_updated_at, created_at
        FROM `{table_name}`
        WHERE request_id = :rid
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        row = conn.execute(sql, {"rid": str(request_id)}).mappings().first()
    return dict(row) if row else None


def create_session(
    *,
    record_id: int,
    count: int,
    meta_input: Any,
    meta_output: Any,
    zip: str | None,
    request_id: str,
    zip_status: str = "pending",
    table_name: str,
) -> Dict[str, Any]:
    """插入一条 session（非幂等）。

    说明：
    - meta_input/meta_output 支持 dict/list，会自动转为 JSON 字符串
    """
    mi = meta_input if isinstance(meta_input, str) else json.dumps(meta_input, ensure_ascii=False)
    mo = meta_output if isinstance(meta_output, str) else json.dumps(meta_output, ensure_ascii=False)
    now = datetime.now(timezone(timedelta(hours=8)))
    sql = text(
        f"""
        INSERT INTO `{table_name}`
        (record_id, count, meta_input, meta_output, zip, request_id, zip_status, zip_updated_at, created_at)
        VALUES (:rid, :cnt, :mi, :mo, :zip, :request_id, :zip_status, :zip_updated_at, :created_at)
        """
    )
    engine = get_mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(
            sql,
            {
                "rid": int(record_id),
                "cnt": int(count),
                "mi": mi,
                "mo": mo,
                "zip": zip or "",
                "request_id": str(request_id),
                "zip_status": str(zip_status or "pending"),
                "zip_updated_at": None,
                "created_at": now,
            },
        )
        new_id = result.lastrowid
        ret = conn.execute(
            text(
                f"SELECT id, record_id, count, meta_input, meta_output, zip, request_id, zip_status, zip_updated_at, created_at FROM `{table_name}` WHERE id = :id"
            ),
            {"id": new_id},
        ).mappings().first()
    return dict(ret) if ret else {}


def create_session_idempotent(
    *, record_id: int, request_id: str, meta_input: Any, meta_output: Any, table_name: str
) -> Tuple[Dict[str, Any], bool]:
    """幂等插入一条 session，并返回 (row, created)。

    约定：
    - request_id 必须是唯一键（同一 request_id 重复调用只会返回已存在行）
    - count 使用当前 record_id 的 MAX(count)+1 计算
    """
    existed = get_session_by_request_id(request_id=str(request_id), table_name=table_name)
    if existed:
        return existed, False
    next_count = get_last_count(record_id=int(record_id), table_name=table_name) + 1
    mi = meta_input if isinstance(meta_input, str) else json.dumps(meta_input, ensure_ascii=False)
    mo = meta_output if isinstance(meta_output, str) else json.dumps(meta_output, ensure_ascii=False)
    now = datetime.now(timezone(timedelta(hours=8)))
    sql = text(
        f"""
        INSERT INTO `{table_name}`
        (record_id, count, meta_input, meta_output, zip, request_id, zip_status, zip_updated_at, created_at)
        VALUES (:record_id, :count, :meta_input, :meta_output, :zip, :request_id, :zip_status, :zip_updated_at, :created_at)
        ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)
        """
    )
    engine = get_mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(
            sql,
            {
                "record_id": int(record_id),
                "count": int(next_count),
                "meta_input": mi,
                "meta_output": mo,
                "zip": "",
                "request_id": str(request_id),
                "zip_status": "pending",
                "zip_updated_at": None,
                "created_at": now,
            },
        )
        sid = int(result.lastrowid or 0)
        row = conn.execute(
            text(
                f"SELECT id, record_id, count, meta_input, meta_output, zip, request_id, zip_status, zip_updated_at, created_at FROM `{table_name}` WHERE id = :id"
            ),
            {"id": sid},
        ).mappings().first()
    return (dict(row) if row else {}), True


def update_session_zip_if_pending(
    *, session_id: int, zip_text: str, zip_status: str = "done", table_name: str
) -> bool:
    """在 zip 仍为空且状态未 done 时，写入 zip 并更新状态（用于 Worker 幂等更新）。"""
    sql = text(
        f"""
        UPDATE `{table_name}`
        SET zip = :zip, zip_status = :zip_status, zip_updated_at = :zip_updated_at
        WHERE id = :id
          AND (zip IS NULL OR zip = '')
          AND (zip_status IS NULL OR zip_status != 'done')
        """
    )
    now = datetime.now(timezone(timedelta(hours=8)))
    engine = get_mysql_engine()
    with engine.begin() as conn:
        res = conn.execute(
            sql,
            {"id": int(session_id), "zip": str(zip_text or ""), "zip_status": str(zip_status), "zip_updated_at": now},
        )
        try:
            return int(res.rowcount or 0) > 0
        except Exception:
            return False

# 排序字段白名单（外部字段 -> 数据库列名）
SORT_MAPPING = {
    "id": "id",
    "count": "count",
    "createdAt": "created_at",
}


def _sanitize_sort(sort_field: str) -> str:
    """将外部排序字段映射为数据库列名，避免任意列名注入到 ORDER BY。"""
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
