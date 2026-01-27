from langchain_openai import ChatOpenAI
from typing import Optional

from agentlz.config.settings import Settings
from .logger import setup_logging


def get_model(settings: Settings, streaming: bool = False) -> ChatOpenAI:
    """默认返回 chat 聊天agent

    参数:
        settings: 应用配置对象
        streaming: 是否启用流式输出，默认为False
        
    返回值:
        ChatOpenAI: 配置好的聊天模型实例
        
    异常:
        无显式异常抛出，但会记录警告日志
    """
    logger = setup_logging(settings.log_level)
    
    common_kwargs = {
        "model": settings.model_name,
        "temperature": settings.model_temperature,
        "streaming": streaming,
    }
    
    if settings.chatopenai_api_key and settings.chatopenai_base_url:
        return ChatOpenAI(
            **common_kwargs,
            api_key=settings.chatopenai_api_key,
            base_url=settings.chatopenai_base_url,
        )
    elif settings.openai_api_key:
        return ChatOpenAI(
            **common_kwargs,
            api_key=settings.openai_api_key,
        )
    else:
        logger.warning("No valid API key found for model configuration. [没有找到有效的API密钥]")
        return None


def get_model_by_name(
    settings: Settings,
    model_name: str,
    streaming: bool = False,
    chatopenai_api_key: Optional[str] = None,
    chatopenai_base_url: Optional[str] = None,
    openai_api_key: Optional[str] = None,
) -> ChatOpenAI:
    """Return a configured chat model instance with explicit model name override.

    参数:
        settings: 应用配置对象
        model_name: 指定的模型名称（覆盖默认 settings.model_name）
        streaming: 是否启用流式输出，默认为False

    返回值:
        ChatOpenAI: 配置好的聊天模型实例

    说明:
        与 get_model 同逻辑，但允许通过传入的 model_name 指定具体模型，
        例如用于图像解析模型（如 GLM-4.1V）。
    """
    logger = setup_logging(settings.log_level)

    common_kwargs = {
        "model": model_name or settings.model_name,
        "temperature": settings.model_temperature,
        "streaming": streaming,
    }

    if chatopenai_api_key and chatopenai_base_url:
        return ChatOpenAI(
            **common_kwargs,
            api_key=chatopenai_api_key,
            base_url=chatopenai_base_url,
        )
    elif openai_api_key:
        return ChatOpenAI(
            **common_kwargs,
            api_key=openai_api_key,
        )
    elif settings.chatopenai_api_key and settings.chatopenai_base_url:
        return ChatOpenAI(
            **common_kwargs,
            api_key=settings.chatopenai_api_key,
            base_url=settings.chatopenai_base_url,
        )
    elif settings.openai_api_key:
        return ChatOpenAI(
            **common_kwargs,
            api_key=settings.openai_api_key,
        )
    else:
        logger.warning("No valid API key found for model configuration. [没有找到有效的API密钥]")
        return None
