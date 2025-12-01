from langchain.tools import tool
import json
from agentlz.core.logger import setup_logging
from agentlz.config.settings import get_settings
from agentlz.services.mcp_service import search_mcp_agents_service
from agentlz.repositories.mcp_repository import search_mcp_by_keyword, to_tool_config, get_mcp_agents_by_ids

@tool
def get_mcp_config_by_keyword(keyword: str) -> str:
    """
    按查询语义检索 MCP（pgvector 混合排序，融合可信度），返回工具配置列表。

    行为：使用 search_mcp_agents_service(query) → ranked rows → 映射为 {name,transport,command,args}
    说明：args 字段可能为空（PG 结果不含 args），将以 [] 兜底。
    """
    settings = get_settings()
    logger = setup_logging(settings.log_level)
  
    try:
        kw = (keyword or "").strip()
        if not kw:
            logger.warning("关键词为空，返回空列表")
            return json.dumps([], ensure_ascii=False)
        rows = search_mcp_agents_service(kw, tenant_id=getattr(settings, "tenant_id_header", "default"))
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
