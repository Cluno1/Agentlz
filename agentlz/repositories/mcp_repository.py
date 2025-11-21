import os
import json
from typing import Any, Dict, List

import pymysql
from agentlz.config.settings import get_settings

# 创建MySQL连接
def _get_conn() -> pymysql.connections.Connection:
    """创建 MySQL 连接（DictCursor）。"""
    # 使用Settings 读取配置
    db_settings = get_settings()
    host = db_settings.db_host or os.getenv("DB_HOST", "localhost")
    port = int(db_settings.db_port or os.getenv("DB_PORT", "3306"))
    user = db_settings.db_user or os.getenv("DB_USER", "root")
    password = db_settings.db_password or os.getenv("DB_PASSWORD", "")
    db = db_settings.db_name or os.getenv("DB_NAME", "agentlz")
    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        db=db,
        charset="utf8mb4",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


# 按关键词模糊搜索 MCP 配置
def search_mcp_by_keyword(keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
    """按关键词在 name/description 模糊匹配，并按 trust_score 降序返回。"""
    conn = _get_conn()  # 失败时直接抛异常，不做兜底
    try:
        like = f"%{keyword}%"
        sql = (
            "SELECT id, name, transport, command, args, category, trust_score, description "
            "FROM mcp_agents "
            "WHERE name LIKE %s OR description LIKE %s "
            "ORDER BY trust_score DESC "
            "LIMIT %s"
        )
        with conn.cursor() as cur:
            cur.execute(sql, (like, like, limit))
            rows = cur.fetchall()
    finally:
        try:
            conn.close()
        except Exception:
            pass

    # 规范化 args 字段为 List[str]
    for r in rows:
        args = r.get("args")
        if isinstance(args, str):
            try:
                r["args"] = json.loads(args)
            except Exception:
                r["args"] = [args]
        elif not isinstance(args, list):
            r["args"] = []
    return rows

# 转换为工具配置字典
def to_tool_config(row: Dict[str, Any]) -> Dict[str, Any]:
    """将数据库行转换为工具配置字典（与 WorkflowPlan.mcp_config 对齐）。"""
    return {
        "name": row.get("name", ""),
        "transport": row.get("transport", "stdio"),
        "command": row.get("command", "python"),
        "args": row.get("args", []),
    }


# 根据ID列表查询mcp配置
def get_mcp_agents_by_ids(ids: List[int]) -> List[Dict[str, Any]]:
    """根据 ID 列表批量查询 MCP 代理配置（MySQL）。"""
    if not ids:
        return []
    placeholders = ",".join(["%s"] * len(ids))
    sql = (
        f"SELECT id, name, transport, command, args, category, trust_score, description FROM mcp_agents WHERE id IN ({placeholders})"
    )
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, ids)
            rows = cur.fetchall()
    finally:
        try:
            conn.close()
        except Exception:
            pass
    for r in rows:
        a = r.get("args")
        if isinstance(a, str):
            try:
                r["args"] = json.loads(a)
            except Exception:
                r["args"] = [a]
        elif not isinstance(a, list):
            r["args"] = []
    return rows

# 插入 MCP 代理记录
def create_mcp_agent(payload: Dict[str, Any]) -> Dict[str, Any]:
    """插入 MCP 代理记录并返回完整行（MySQL）。"""
    name = payload.get("name") or ""
    transport = payload.get("transport") or "stdio"
    command = payload.get("command") or "python"
    args = payload.get("args")
    description = payload.get("description") or ""
    category = payload.get("category")
    trust_score = float(payload.get("trust_score", 0))
    if isinstance(args, (list, dict)):
        args_str = json.dumps(args, ensure_ascii=False)
    elif isinstance(args, str):
        args_str = args
    else:
        args_str = json.dumps([], ensure_ascii=False)
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO mcp_agents (name, transport, command, args, description, category, trust_score) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (name, transport, command, args_str, description, category, trust_score),
            )
            new_id = cur.lastrowid
            cur.execute(
                "SELECT id, name, transport, command, args, category, trust_score, description FROM mcp_agents WHERE id=%s",
                (new_id,),
            )
            row = cur.fetchone()
    finally:
        try:
            conn.close()
        except Exception:
            pass
    if isinstance(row.get("args"), str):
        try:
            row["args"] = json.loads(row["args"])
        except Exception:
            row["args"] = [row["args"]]
    return row


# 更新 MCP 代理记录
def update_mcp_agent(agent_id: int, payload: Dict[str, Any]) -> Dict[str, Any] | None:
    """更新 MCP 代理记录并返回最新行（MySQL）。"""
    allowed = ["name", "transport", "command", "args", "description", "category", "trust_score"]
    sets: List[str] = []
    values: List[Any] = []
    for col in allowed:
        if col in payload and payload[col] is not None:
            val = payload[col]
            if col == "args":
                if isinstance(val, (list, dict)):
                    val = json.dumps(val, ensure_ascii=False)
                elif not isinstance(val, str):
                    val = json.dumps([], ensure_ascii=False)
            sets.append(f"{col}=%s")
            values.append(val)
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            if sets:
                sql = "UPDATE mcp_agents SET " + ", ".join(sets) + " WHERE id=%s"
                cur.execute(sql, (*values, agent_id))
            cur.execute(
                "SELECT id, name, transport, command, args, category, trust_score, description FROM mcp_agents WHERE id=%s",
                (agent_id,),
            )
            row = cur.fetchone()
    finally:
        try:
            conn.close()
        except Exception:
            pass
    if not row:
        return None
    if isinstance(row.get("args"), str):
        try:
            row["args"] = json.loads(row["args"])
        except Exception:
            row["args"] = [row["args"]]
    return row