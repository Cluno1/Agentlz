
from typing import Optional

from agentlz.config.settings import get_settings
from agentlz.core.logger import setup_logging

try:
    # LangChain 1.x 推荐从 langchain_community 引入 HuggingFaceEmbeddings
    from langchain_community.embeddings import HuggingFaceEmbeddings
except Exception:  # 兼容旧版本，必要时可回退
    try:
        from langchain.embeddings import HuggingFaceEmbeddings  # type: ignore
    except Exception:
        HuggingFaceEmbeddings = None  # 延迟到运行时检查



def get_hf_embeddings(
    model_name: Optional[str] = "BAAI/bge-small-zh-v1.5",
    device: Optional[str] = "cpu",
    normalize_embeddings: bool = True,
):
    """
    创建并返回一个 HuggingFace 中文句向量嵌入模型（LangChain 兼容）。

    参数:
        model_name: 模型名称或本地路径，默认使用 "BAAI/bge-small-zh-v1.5"
        device: 设备标识（如 "cpu"/"cuda"），不传则默认 cpu
        normalize_embeddings: 是否归一化向量，默认 True

    返回:
        HuggingFaceEmbeddings 实例

    异常:
        RuntimeError: 当环境缺失 HuggingFaceEmbeddings 依赖时抛出
    """
    
    settings = get_settings()
    logger = setup_logging(settings.log_level)

    if HuggingFaceEmbeddings is None:
        raise RuntimeError(
            "未找到 HuggingFaceEmbeddings，请安装 langchain-community 和 sentence-transformers。"
        )

    # 允许通过环境变量覆盖
    name = model_name or settings.hf_embedding_model or "BAAI/bge-small-zh-v1.5"

    model_kwargs = {}
    if device:
        model_kwargs["device"] = device

    encode_kwargs = {"normalize_embeddings": normalize_embeddings}

    logger.info(f"加载 Embeddings 模型: {name} (device={device or 'auto'})")
    return HuggingFaceEmbeddings(
        model_name=name,
        model_kwargs=model_kwargs if model_kwargs else {},
        encode_kwargs=encode_kwargs,
    )
