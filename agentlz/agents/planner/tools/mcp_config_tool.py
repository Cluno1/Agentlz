from langchain.tools import tool
from typing import List, Dict
import json


@tool
def get_mcp_config_by_keyword(keyword: str) -> str:
    """
    按关键词查询 MCP（name/description LIKE 匹配），按 trust_score 降序返回。
    SQL: SELECT id, name, transport, command, args, category, trust_score, description
         FROM mcp_agents
         WHERE name LIKE CONCAT('%', :kw, '%') OR description LIKE CONCAT('%', :kw, '%')
         ORDER BY trust_score DESC
         LIMIT 10;
    """
    from agentlz.repositories.mcp_repository import search_mcp_by_keyword, to_tool_config
    rows = search_mcp_by_keyword(keyword, limit=3)
    print(f"🔍 按关键词查询 MCP 结果: {rows}")
    result = [to_tool_config(r) for r in rows]
    # 工具输出必须是字符串，避免下游 OpenAI Chat Completions 对 messages.content 的类型错误
    return json.dumps(result, ensure_ascii=False)