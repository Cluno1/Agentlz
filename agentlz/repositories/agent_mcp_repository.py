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
        ORDER BY id DESC
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        rows = conn.execute(sql, {"agent_id": agent_id}).mappings().all()
    return [dict(r) for r in rows]


def get_agent_mcp_by_id(*, rel_id: int, table_name: str) -> Optional[Dict[str, Any]]:
    """按主键查询单条关联记录。"""
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
    now = datetime.now(timezone.utc)
    sql = text(
        f"""
        INSERT INTO `{table_name}`
        (agent_id, mcp_agent_id, created_at)
        VALUES (:agent_id, :mcp_agent_id, :created_at)
        """
    )
    params = {
        "agent_id": payload.get("agent_id"),
        "mcp_agent_id": payload.get("mcp_agent_id"),
        "created_at": now,
    }
    engine = get_mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(sql, params)
        new_id = result.lastrowid
        ret = conn.execute(
            text(
                f"SELECT id, agent_id, mcp_agent_id, created_at FROM `{table_name}` WHERE id = :id"
            ),
            {"id": new_id},
        ).mappings().first()
        return dict(ret)


def delete_agent_mcp(*, rel_id: int, table_name: str) -> bool:
    """按主键删除关联记录。"""
    sql = text(f"DELETE FROM `{table_name}` WHERE id = :id")
    engine = get_mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(sql, {"id": rel_id})
        return result.rowcount > 0


def delete_agent_mcp_by_pair(*, agent_id: int, mcp_agent_id: int, table_name: str) -> bool:
    """按唯一键 `(agent_id, mcp_agent_id)` 删除关联记录。"""
    sql = text(f"DELETE FROM `{table_name}` WHERE agent_id = :agent_id AND mcp_agent_id = :mcp_agent_id")
    engine = get_mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(sql, {"agent_id": agent_id, "mcp_agent_id": mcp_agent_id})
        return result.rowcount > 0