from langchain_openai import ChatOpenAI

from ..config.settings import Settings
from .logger import setup_logging


def get_model(settings: Settings, streaming: bool = False) -> ChatOpenAI:
    """Return a configured chat model instance.

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
