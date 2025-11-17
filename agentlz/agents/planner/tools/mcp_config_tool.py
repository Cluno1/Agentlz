from langchain.tools import tool
import json
from agentlz.core.logger import setup_logging
from agentlz.config.settings import get_settings
from agentlz.repositories.mcp_repository import search_mcp_by_keyword, to_tool_config

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
    settings = get_settings()
    logger = setup_logging(settings.log_level)
  
    try:
        kw = (keyword or "").strip()
        if not kw:
            logger.warning("关键词为空，返回空列表")
            return json.dumps([], ensure_ascii=False)
        rows = search_mcp_by_keyword(kw, limit=3)
        logger.info("🔍 按关键词查询 MCP 结果: %s", rows)
        result = [to_tool_config(r) for r in rows]
        # 工具输出必须是字符串，避免下游 OpenAI Chat Completions 对 messages.content 的类型错误
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.exception("查询 MCP 失败：%r", e)
        return json.dumps([], ensure_ascii=False)
