from __future__ import annotations
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from agentlz.core.model_factory import get_model
from agentlz.config.settings import get_settings
from agentlz.schemas.chunk_semantic import ChunkSemanticInput, ChunkSemanticOutput
from agentlz.prompts.rag.chunk_semantic import CHUNK_SEMANTIC_SYSTEM_PROMPT


def get_chunk_semantic_agent() -> Runnable[ChunkSemanticInput, ChunkSemanticOutput]:
    """
    构建并返回一个“语义切片代理”（LLM 驱动）
    
    输入：ChunkSemanticInput(content: str, chunk_size: int)
    输出：ChunkSemanticOutput(segments: List[str])
    
    设计说明：
    - 使用系统提示 CHUNK_SEMANTIC_SYSTEM_PROMPT 指导模型执行主题化、结构保持的分段任务；
    - 当模型未配置时（get_model 返回 None），直接返回提示词链（不绑定结构化输出），调用方需做回退；
    - 正常情况下，绑定结构化输出为 ChunkSemanticOutput，确保严格 JSON 返回与解析。
    """
    settings = get_settings()
    llm = get_model(settings=settings)
    prompt = ChatPromptTemplate.from_messages([
        ("system", CHUNK_SEMANTIC_SYSTEM_PROMPT),
        ("human", "content:\n{content}\n\nchunk_size: {chunk_size}"),
    ])
    if llm is None:
        return prompt
    structured_llm = llm.with_structured_output(ChunkSemanticOutput)
    return prompt | structured_llm

