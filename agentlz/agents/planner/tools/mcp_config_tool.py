from langchain.tools import tool
import json
from agentlz.core.logger import setup_logging
from agentlz.config.settings import get_settings
from agentlz.services.mcp_service import search_mcp_agents_service
from agentlz.repositories.mcp_repository import search_mcp_by_keyword, to_tool_config, get_mcp_agents_by_ids

@tool
def get_mcp_config_by_keyword(keyword: str, user_id: int | None = None, tenant_id: str | None = None) -> str:
    """
    按查询语义检索 MCP（pgvector 混合排序，融合可信度），返回工具配置列表。
    行为：search_mcp_agents_service → MySQL 剪枝 → PG 向量 → 补全 args → JSON 工具配置
    """
    settings = get_settings()
    logger = setup_logging(settings.log_level)
  
    try:
        kw = (keyword or "").strip()
        if not kw:
            logger.warning("关键词为空，返回空列表")
            return json.dumps([], ensure_ascii=False)
        rows = search_mcp_agents_service(kw, tenant_id=(tenant_id or "default"), user_id=user_id)
        logger.info("🔍 按查询 '%s' 的 MCP 混合检索结果: %s", kw, rows)
        if not rows:
            fallback = search_mcp_by_keyword(kw, limit=10)
            logger.info("🔁 混合检索为空，回退 MySQL 关键词 '%s' 结果: %s", kw, fallback)
            rows = fallback
        ids = [int(r.get("id")) for r in rows if str(r.get("id", "")).isdigit()]
        args_map = {}
        if ids:
            mysql_rows = get_mcp_agents_by_ids(ids)
            for mr in mysql_rows:
                mid = int(mr.get("id"))
                args_map[mid] = mr.get("args", [])
        enriched = []
        for r in rows:
            rid = int(r.get("id")) if str(r.get("id", "")).isdigit() else None
            if rid is not None and rid in args_map:
                rr = dict(r)
                rr["args"] = args_map[rid]
                enriched.append(rr)
            else:
                enriched.append(r)
        if args_map:
            logger.info("🔧 已依据 MySQL args 补全 %d 条记录", len(args_map))
        result = [to_tool_config(r) for r in enriched]
        # 工具输出必须是字符串，避免下游 OpenAI Chat Completions 对 messages.content 的类型错误
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.exception("查询 MCP 失败：%r", e)
        return json.dumps([], ensure_ascii=False)

def make_mcp_keyword_tool(user_id: int | None, tenant_id: str | None = None):
    """按请求上下文绑定用户身份，返回仅接受 keyword 的工具。

    LLM 工具调用签名保持简单（keyword），内部通过闭包将 user_id、传入检索服务，避免全局状态并提升并发安全性。
    """
    @tool(name="search_mcp") 
    def search_mcp(keyword: str) -> str:
        """
        根据自然语言关键词搜索 MCP 工具，返回可用工具配置列表。
        参数
        ----
        keyword : str
            你想找的工具关键词，例如 "PDF 解析" 或 "数据库连接"。
        返回
        ----
        str
            JSON 字符串，内含工具名、transport、command、args 等配置。
        """
        return get_mcp_config_by_keyword(keyword, user_id=user_id, tenant_id=tenant_id)
    return search_mcp
