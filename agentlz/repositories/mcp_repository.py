import os
import json
from typing import Any, Dict, List

import pymysql
from agentlz.config.settings import get_settings


def _get_conn() -> pymysql.connections.Connection:
    """创建 MySQL 连接（DictCursor）。"""
    # 使用Settings 读取配置
    db_settings = get_settings()
    host = db_settings.db_host or os.getenv("DB_HOST", "localhost")
    port = int(db_settings.db_port or os.getenv("DB_PORT", "3306"))
    user = db_settings.db_user or os.getenv("DB_USER", "root")
    password = db_settings.db_password or os.getenv("DB_PASSWORD", "")
    db = db_settings.db_name or os.getenv("DB_NAME", "agentlz-mcp")
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


def to_tool_config(row: Dict[str, Any]) -> Dict[str, Any]:
    """将数据库行转换为工具配置字典（与 WorkflowPlan.mcp_config 对齐）。"""
    return {
        "name": row.get("name", ""),
        "transport": row.get("transport", "stdio"),
        "command": row.get("command", "python"),
        "args": row.get("args", []),
        # 可扩展：category / trust_score / description 由上层按需使用
    }