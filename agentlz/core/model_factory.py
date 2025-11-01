from langchain_openai import ChatOpenAI

from ..config.settings import Settings
from .logger import setup_logging


def get_model(settings: Settings) -> ChatOpenAI:
    """Return a configured chat model instance.

    This factory is minimal but structured for future provider extensions.
    """
    logger = setup_logging(settings.log_level)
    
    if settings.chatopenai_api_key and settings.chatopenai_base_url:
        return ChatOpenAI(
            model=settings.model_name,
            temperature=settings.model_temperature,
            api_key=settings.chatopenai_api_key,
            base_url=settings.chatopenai_base_url,
        )
    elif settings.openai_api_key:
        return ChatOpenAI(
            model=settings.model_name,
            temperature=settings.model_temperature,
            api_key=settings.openai_api_key,
        )
    else:
        logger.warning("No valid API key found for model configuration. [没有找到有效的API密钥]")
        return None
