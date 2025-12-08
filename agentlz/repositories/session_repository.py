from __future__ import annotations

"""会话仓储（MySQL）

职责
- 仅负责读取指定记录（record_id）下的会话原始数据
- 保持 SQL 与数据访问纯净，不做裁剪/解析（服务层负责）

实现说明
- 所有 SQL 使用参数化（sqlalchemy.text）
"""

from typing import Any, Dict, List
from sqlalchemy import text

from agentlz.core.database import get_mysql_engine


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

