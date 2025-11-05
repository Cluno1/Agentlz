from typing import Any

from langchain.agents import create_agent

from ..config.settings import get_settings
from ..core.model_factory import get_model
from ..tools.markdown import convert_to_markdown


MARKDOWN_SYSTEM_PROMPT = """
你是一个 Markdown 转换助手。接收任何输入（文本、文件路径、URL）。
当需要转换内容为 Markdown 时，调用工具 convert_to_markdown(input_value)。
功能要求：
- 支持本地文件：PDF、DOCX、XLSX、PPTX、图片、音频（自动转录）。
- 支持网页：普通网页、YouTube 链接（转录字幕）。
- 支持搜索：对纯文本查询或以 `bing:` 开头的查询返回搜索结果的 Markdown 汇总。
请直接输出 Markdown 内容，不要添加额外说明。
"""


def build_markdown_agent():
    settings = get_settings()
    model = get_model(settings)
    agent = create_agent(
        model=model,
        tools=[convert_to_markdown],
        system_prompt=MARKDOWN_SYSTEM_PROMPT,
    )
    return agent


def ask(message: str) -> str:
    """Convert any input to Markdown via the agent and return text."""
    agent = build_markdown_agent()
    result: Any = agent.invoke({"messages": [{"role": "user", "content": message}]})

    if isinstance(result, dict):
        return (
            result.get("output")
            or result.get("final_output")
            or result.get("structured_response")
            or str(result)
        )
    return str(result)