from typing import Dict, Any

from langchain.agents import create_agent

from agentlz.tools.search import get_search

from ..config.settings import get_settings
from ..core.model_factory import get_model
from ..prompts.templates import THESIS_SYSTEM_PROMPT
from ..schemas.responses import ThesisResponse


def build_thesis_agent():
    """构建论文检索Agent"""
    settings = get_settings()
    model = get_model(settings)
    agent = create_agent(
        model=model,
        tools=[get_search],  # 这里可以添加论文检索相关的工具
        system_prompt=THESIS_SYSTEM_PROMPT,
    )
    return agent


def get_thesis_info(query: str) -> ThesisResponse:
    """获取论文信息
    
    Args:
        query: 用户的论文查询请求
        
    Returns:
        ThesisResponse: 论文信息响应
    """
    agent = build_thesis_agent()
    result: Dict[str, Any] = agent.invoke({"messages": [{"role": "user", "content": query}]})
    
    # 解析返回结果为ThesisResponse对象
    if isinstance(result, dict):
        return ThesisResponse(
            title=result.get("title", ""),
            authors=result.get("authors", []),
            abstract=result.get("abstract", ""),
            url=result.get("url"),
            year=result.get("year"),
            citations=result.get("citations")
        )
    