from __future__ import annotations
import base64
import mimetypes
import os
from typing import Any

from langchain_core.messages import SystemMessage, HumanMessage
from agentlz.config.settings import get_settings
from agentlz.core.model_factory import get_model_by_name
from agentlz.prompts.tools.image_analyze import IMAGE_ANALYZE_SYSTEM_PROMPT
from agentlz.schemas.image_analyze import ImageAnalyzeInput, ImageAnalyzeOutput


def _image_to_data_url(image_path: str) -> str:
    """将本地图片文件转换为 data URL（base64）。支持 png/jpeg/jpg。"""
    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"图片文件不存在: {image_path}")
    mime, _ = mimetypes.guess_type(image_path)
    if not mime or not mime.startswith("image/"):
        # 默认回退为 png
        mime = "image/png"
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def get_image_analyze_agent():
    """
    构建并返回一个“图像解析代理”。

    输入：ImageAnalyzeInput(image_path: str, prefer_task: Literal['auto','text','table'])
    输出：ImageAnalyzeOutput(main_features, format_type, extracted_text, table_markdown)

    说明：
    - 使用专属图像模型（settings.image_analyze_model_name）。
    - 通过结构化输出约束，确保返回字段稳定可解析。
    """
    settings = get_settings()
    model_name = getattr(settings, "image_analyze_model_name", None)
    llm = get_model_by_name(settings=settings, model_name=model_name)
    if llm is None:
        return None
    structured_llm = llm.with_structured_output(ImageAnalyzeOutput)

    class _ImageAgent:
        def __init__(self, base_model):
            self._base = base_model

        def invoke(self, input_data: ImageAnalyzeInput) -> ImageAnalyzeOutput | dict | str:
            # 构造 data URL 图片内容
            data_url = _image_to_data_url(input_data.image_path)
            prefer = input_data.prefer_task or "auto"
            # 组织消息：system 提示 + human 文本与图像
            messages = [
                SystemMessage(content=IMAGE_ANALYZE_SYSTEM_PROMPT),
                HumanMessage(content=[
                    {"type": "text", "text": f"任务偏好: {prefer}. 请解析并按规范输出。"},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ]),
            ]
            return self._base.invoke(messages)

    return _ImageAgent(structured_llm)


def analyze_image(image_path: str) -> str:
    """
    便捷函数：输入本地图片路径，返回整合后的文本描述。

    输出包含：
    - 图片主体特征（按行列出）
    - 若为表格，附带 Markdown 表格；否则给出完整文字提取
    """
    agent = get_image_analyze_agent()
    if agent is None:
        return "图像解析失败：模型未配置，请在 .env 设置 CHATOPENAI_API_KEY/CHATOPENAI_BASE_URL 或 OPENAI_API_KEY，以及 IMAGE_ANALYZE_MODEL_NAME"
    try:
        resp: Any = agent.invoke(ImageAnalyzeInput(image_path=image_path))
    except Exception as e:
        return f"图像解析错误：{e}"

    # 兼容不同返回类型（结构化/字典/字符串）
    if isinstance(resp, ImageAnalyzeOutput):
        feats = "\n".join(f"- {x}" for x in (resp.main_features or []))
        if resp.format_type in ("table", "mixed") and resp.table_markdown:
            return f"主体特征:\n{feats}\n\n表格重建:\n{resp.table_markdown}\n\n文字汇总:\n{resp.extracted_text}"
        return f"主体特征:\n{feats}\n\n文字提取:\n{resp.extracted_text}"
    if isinstance(resp, dict):
        feats = "\n".join(f"- {x}" for x in resp.get("main_features", []) or [])
        fmt = resp.get("format_type", "text")
        text = str(resp.get("extracted_text", ""))
        table = str(resp.get("table_markdown", ""))
        if fmt in ("table", "mixed") and table:
            return f"主体特征:\n{feats}\n\n表格重建:\n{table}\n\n文字汇总:\n{text}"
        return f"主体特征:\n{feats}\n\n文字提取:\n{text}"
    return str(resp)