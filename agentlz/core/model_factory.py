from langchain_openai import ChatOpenAI
from typing import Optional

from agentlz.config.settings import Settings
from .logger import setup_logging


def _deepseek_extra_body(base_url: Optional[str]) -> Optional[dict]:
    """DeepSeek 官方 endpoint 自动注入 thinking=disabled 关掉推理。

    背景：DeepSeek v4 系列（deepseek-v4-flash / deepseek-v4-pro）默认开启 thinking 模式，
    响应里含 `reasoning_content` 字段。LangChain `langchain-openai` 在把 OpenAI 响应映射成
    `AIMessage` 时**丢失** `reasoning_content`；多轮 tool 调用时序列化回去的 assistant
    message 没有该字段，DeepSeek 服务端拒绝并报：
      'The `reasoning_content` in the thinking mode must be passed back to the API.'

    通过 OpenAI SDK 的 `extra_body` 机制把 `thinking={"type":"disabled"}` 透传到请求体，
    在请求侧关掉推理，根治 langchain-openai ↔ DeepSeek 多轮交互兼容问题。

    仅对 base_url 含 `deepseek.com` 的官方 endpoint 生效；中转/兼容上游不受影响。
    DeepSeek 官方 `thinking.type` 合法枚举：adaptive / enabled / disabled。
    """
    if not base_url:
        return None
    if "deepseek.com" not in base_url.lower():
        return None
    return {"thinking": {"type": "disabled"}}


def _build_chat_openai(common_kwargs: dict, *, api_key: str, base_url: Optional[str] = None) -> ChatOpenAI:
    """统一构造 ChatOpenAI，按 base_url 决定是否注入 extra_body。"""
    kwargs = dict(common_kwargs)
    kwargs["api_key"] = api_key
    if base_url:
        kwargs["base_url"] = base_url
        extra = _deepseek_extra_body(base_url)
        if extra:
            kwargs["extra_body"] = extra
    return ChatOpenAI(**kwargs)


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
        "timeout": float(getattr(settings, "model_request_timeout", 60.0) or 60.0),
        "max_retries": int(getattr(settings, "model_max_retries", 1) or 1),
    }
    
    if settings.chatopenai_api_key and settings.chatopenai_base_url:
        return _build_chat_openai(
            common_kwargs,
            api_key=settings.chatopenai_api_key,
            base_url=settings.chatopenai_base_url,
        )
    elif settings.openai_api_key:
        return _build_chat_openai(common_kwargs, api_key=settings.openai_api_key)
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
        "timeout": float(getattr(settings, "model_request_timeout", 60.0) or 60.0),
        "max_retries": int(getattr(settings, "model_max_retries", 1) or 1),
    }

    if chatopenai_api_key and chatopenai_base_url:
        return _build_chat_openai(
            common_kwargs, api_key=chatopenai_api_key, base_url=chatopenai_base_url
        )
    elif openai_api_key:
        return _build_chat_openai(common_kwargs, api_key=openai_api_key)
    elif settings.chatopenai_api_key and settings.chatopenai_base_url:
        return _build_chat_openai(
            common_kwargs,
            api_key=settings.chatopenai_api_key,
            base_url=settings.chatopenai_base_url,
        )
    elif settings.openai_api_key:
        return _build_chat_openai(common_kwargs, api_key=settings.openai_api_key)
    else:
        logger.warning("No valid API key found for model configuration. [没有找到有效的API密钥]")
        return None
