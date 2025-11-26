import os
import json
from typing import Any, Dict, List

from sqlalchemy import text
from agentlz.core.database import get_mysql_engine


# 按关键词模糊搜索 MCP 配置
def search_mcp_by_keyword(keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
    """按关键词在 name/description 模糊匹配，并按 trust_score 降序返回。"""
    like = f"%{keyword}%"
    engine = get_mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT id, name, transport, command, args, category, trust_score, description "
                "FROM mcp_agents "
                "WHERE name LIKE :like1 OR description LIKE :like2 "
                "ORDER BY trust_score DESC "
                "LIMIT :limit"
            ),
            {"like1": like, "like2": like, "limit": limit},
        )
        rows = [dict(r._mapping) for r in result.fetchall()]

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
    engine = get_mysql_engine()
    names = {f"id{i}": int(v) for i, v in enumerate(ids)}
    placeholders = ",".join([f":{k}" for k in names.keys()])
    sql = text(
        f"SELECT id, name, transport, command, args, category, trust_score, description FROM mcp_agents WHERE id IN ({placeholders})"
    )
    with engine.begin() as conn:
        result = conn.execute(sql, names)
        rows = [dict(r._mapping) for r in result.fetchall()]
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

# 根据 (name, transport, command) 组合批量查询 MCP 配置，利用联合唯一索引精确命中
def get_mcp_agents_by_unique(triplets: List[tuple[str, str, str]]) -> List[Dict[str, Any]]:
    if not triplets:
        return []
    engine = get_mysql_engine()
    clauses: List[str] = []
    params: Dict[str, Any] = {}
    for i, (n, t, c) in enumerate(triplets):
        params[f"n{i}"] = str(n)
        params[f"t{i}"] = str(t)
        params[f"c{i}"] = str(c)
        clauses.append(f"(name=:n{i} AND transport=:t{i} AND command=:c{i})")
    sql = text(
        "SELECT id, name, transport, command, args, category, trust_score, description FROM mcp_agents WHERE "
        + " OR ".join(clauses)
    )
    with engine.begin() as conn:
        result = conn.execute(sql, params)
        rows = [dict(r._mapping) for r in result.fetchall()]
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
    engine = get_mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO mcp_agents (name, transport, command, args, description, category, trust_score) "
                "VALUES (:name,:transport,:command,:args,:description,:category,:trust_score)"
            ),
            {
                "name": name,
                "transport": transport,
                "command": command,
                "args": args_str,
                "description": description,
                "category": category,
                "trust_score": trust_score,
            },
        )
        new_id = int(getattr(result, "lastrowid", 0) or 0)
        if new_id == 0:
            new_id = conn.execute(text("SELECT LAST_INSERT_ID() AS id")).scalar() or 0
        row_res = conn.execute(
            text(
                "SELECT id, name, transport, command, args, category, trust_score, description FROM mcp_agents WHERE id=:id"
            ),
            {"id": int(new_id)},
        )
        row_map = row_res.fetchone()._mapping
        row = dict(row_map)
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
    params: Dict[str, Any] = {"id": int(agent_id)}
    for col in allowed:
        if col in payload and payload[col] is not None:
            val = payload[col]
            if col == "args":
                if isinstance(val, (list, dict)):
                    val = json.dumps(val, ensure_ascii=False)
                elif not isinstance(val, str):
                    val = json.dumps([], ensure_ascii=False)
            sets.append(f"{col}=:{col}")
            params[col] = val
    engine = get_mysql_engine()
    with engine.begin() as conn:
        if sets:
            sql = text("UPDATE mcp_agents SET " + ", ".join(sets) + " WHERE id=:id")
            conn.execute(sql, params)
        row_res = conn.execute(
            text(
                "SELECT id, name, transport, command, args, category, trust_score, description FROM mcp_agents WHERE id=:id"
            ),
            {"id": int(agent_id)},
        )
        row_obj = row_res.fetchone()
        if not row_obj:
            return None
        row = dict(row_obj._mapping)
    if isinstance(row.get("args"), str):
        try:
            row["args"] = json.loads(row["args"])
        except Exception:
            row["args"] = [row["args"]]
    return row