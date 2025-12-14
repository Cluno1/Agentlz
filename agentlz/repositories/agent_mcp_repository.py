"""Agent‑MCP 关联仓储（MySQL）

职责
- 管理 agent 与 mcp_agents 的关联关系（唯一键 `agent_id + mcp_agent_id`）
- 所有 SQL 使用参数化形式（sqlalchemy.text + 绑定参数），避免 SQL 注入

表结构对齐（参见 `docs/deploy/sql/init_mysql.sql` 的 `agent_mcp` 表）
- 主键：`id` bigint(20)
- 唯一约束：`uk_agent_mcp (agent_id, mcp_agent_id)`
- 索引：`idx_agent_mcp_agent`、`idx_agent_mcp_mcp`

使用约定
- 查询/删除支持主键或唯一对（pair）两种方式
- 新增时避免重复：可在服务层先查 `get_agent_mcp_by_pair`
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from sqlalchemy import text

from agentlz.core.database import get_mysql_engine


def list_agent_mcp(*, agent_id: int, table_name: str) -> List[Dict[str, Any]]:
    """按 agent 列出 MCP 关联列表。"""
    sql = text(
        f"""
        SELECT id, agent_id, mcp_agent_id, created_at
        FROM `{table_name}` WHERE agent_id = :agent_id
        ORDER BY id DESC -- 按主键倒序，最近关联在前
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        # 参数化查询，避免注入
        rows = conn.execute(sql, {"agent_id": agent_id}).mappings().all()
    return [dict(r) for r in rows]


def get_agent_mcp_by_id(*, rel_id: int, table_name: str) -> Optional[Dict[str, Any]]:
    """按主键查询单条关联记录。"""
    # 精确匹配主键
    sql = text(
        f"""
        SELECT id, agent_id, mcp_agent_id, created_at
        FROM `{table_name}` WHERE id = :id
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        row = conn.execute(sql, {"id": rel_id}).mappings().first()
    return dict(row) if row else None


def get_agent_mcp_by_pair(*, agent_id: int, mcp_agent_id: int, table_name: str) -> Optional[Dict[str, Any]]:
    """按唯一键 `(agent_id, mcp_agent_id)` 查询关联记录。"""
    # 使用唯一键对进行查询
    sql = text(
        f"""
        SELECT id, agent_id, mcp_agent_id, created_at
        FROM `{table_name}` WHERE agent_id = :agent_id AND mcp_agent_id = :mcp_agent_id
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        row = conn.execute(sql, {"agent_id": agent_id, "mcp_agent_id": mcp_agent_id}).mappings().first()
    return dict(row) if row else None


def create_agent_mcp(
    *,
    payload: Dict[str, Any],
    table_name: str,
) -> Dict[str, Any]:
    """创建关联并回读插入后的完整记录。"""
    # 记录创建时间（UTC）
    now = datetime.now(timezone.utc)
    # 可选列：permission_type/is_default 若存在则插入
    perm = payload.get("permission_type")
    is_def = payload.get("is_default")
    if perm is not None or is_def is not None:
        sql = text(
            f"""
            INSERT INTO `{table_name}`
            (agent_id, mcp_agent_id, created_at, permission_type, is_default)
            VALUES (:agent_id, :mcp_agent_id, :created_at, :permission_type, :is_default)
            """
        )
    else:
        sql = text(
            f"""
            INSERT INTO `{table_name}`
            (agent_id, mcp_agent_id, created_at)
            VALUES (:agent_id, :mcp_agent_id, :created_at)
            """
        )
    # 参数化插入
    params = {
        "agent_id": payload.get("agent_id"),
        "mcp_agent_id": payload.get("mcp_agent_id"),
        "created_at": now,
        "permission_type": payload.get("permission_type") if perm is not None else None,
        "is_default": int(payload.get("is_default")) if is_def is not None else None,
    }
    engine = get_mysql_engine()
    with engine.begin() as conn:
        # 事务插入并读取新记录
        result = conn.execute(sql, params)
        new_id = result.lastrowid
        ret = conn.execute(
            text(
                f"SELECT id, agent_id, mcp_agent_id, created_at FROM `{table_name}` WHERE id = :id"
            ),
            {"id": new_id},
        ).mappings().first()
        return dict(ret)

def clear_agent_mcp(*, agent_id: int, table_name: str) -> int:
    """清空某 Agent 的 MCP 关系行。

    返回删除条数。
    """
    sql = text(f"DELETE FROM `{table_name}` WHERE agent_id = :agent_id")
    engine = get_mysql_engine()
    with engine.begin() as conn:
        res = conn.execute(sql, {"agent_id": int(agent_id)})
        return int(res.rowcount or 0)

def bulk_insert_agent_mcp(*, agent_id: int, ids: List[int], table_name: str, permission_type: str | None = None) -> int:
    """批量插入 Agent⇄MCP 关系。

    - 当传入 permission_type 时，同时写 is_default=0。
    - 逐条插入，忽略失败记录；返回成功插入条数。
    """
    if not ids:
        return 0
    engine = get_mysql_engine()
    now = datetime.now(timezone.utc)
    inserted = 0
    with engine.begin() as conn:
        for mid in ids:
            try:
                payload = {"agent_id": int(agent_id), "mcp_agent_id": int(mid), "created_at": now}
                if permission_type is not None:
                    payload["permission_type"] = permission_type
                    payload["is_default"] = 0
                sql = text(
                    f"INSERT INTO `{table_name}` (agent_id, mcp_agent_id, created_at"
                    + (", permission_type, is_default" if permission_type is not None else "")
                    + ") VALUES (:agent_id, :mcp_agent_id, :created_at"
                    + (", :permission_type, :is_default" if permission_type is not None else "")
                    + ")"
                )
                conn.execute(sql, payload)
                inserted += 1
            except Exception:
                pass
    return inserted


def delete_agent_mcp(*, rel_id: int, table_name: str) -> bool:
    """按主键删除关联记录。"""
    # 主键删除
    sql = text(f"DELETE FROM `{table_name}` WHERE id = :id")
    engine = get_mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(sql, {"id": rel_id})
        return result.rowcount > 0


def delete_agent_mcp_by_pair(*, agent_id: int, mcp_agent_id: int, table_name: str) -> bool:
    """按唯一键 `(agent_id, mcp_agent_id)` 删除关联记录。"""
    # 唯一键对删除
    sql = text(f"DELETE FROM `{table_name}` WHERE agent_id = :agent_id AND mcp_agent_id = :mcp_agent_id")
    engine = get_mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(sql, {"agent_id": agent_id, "mcp_agent_id": mcp_agent_id})
    return result.rowcount > 0

def clear_agent_mcp_by_mcp_id(*, mcp_agent_id: int, table_name: str) -> int:
    sql = text(f"DELETE FROM `{table_name}` WHERE mcp_agent_id = :mid")
    engine = get_mysql_engine()
    with engine.begin() as conn:
        res = conn.execute(sql, {"mid": int(mcp_agent_id)})
        return int(res.rowcount or 0)
