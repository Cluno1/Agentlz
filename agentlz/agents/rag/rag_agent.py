"""
RAG 代理（占位实现）

本文件提供两类 RAG 能力的占位实现：
- 检索（Retrieve）：按查询语句召回候选文档；当前仅返回空列表作为演示。
- 重排（Rerank）：对候选文档列表进行排序或打分；当前按一个可预测的占位规则赋分。

设计意图
- 保持与实际 RAG 流程一致的接口形态（输入/输出 Schema、代理构造方式）。
- 便于后续替换为真实的向量检索与重排逻辑（如 pgvector/faiss + 嵌入模型）。

使用方式
- 直接函数：`rag_retrieve(...)`、`rag_rerank(...)` 适合在代码中同步调用。
- 代理（LCEL 链）：`get_rag_retrieve_agent()`、`get_rag_rerank_agent()` 返回可 `invoke` 的链，
  与其他 Agent 保持一致的调用体验，便于统一编排。
"""

from typing import List

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from agentlz.core.model_factory import get_model
from agentlz.config.settings import get_settings
from agentlz.schemas.rag import (
    RAGDocument,
    RAGRetrieveInput,
    RAGRetrieveOutput,
    RAGRerankInput,
    RAGRerankOutput,
)
from agentlz.prompts.rag.rag import (
    RAG_RETRIEVE_SYSTEM_PROMPT,
    RAG_RERANK_SYSTEM_PROMPT,
)


def get_rag_retrieve_agent() -> Runnable[RAGRetrieveInput, RAGRetrieveOutput]:
    """
    构建并返回一个“检索占位代理”。

    输入：`RAGRetrieveInput(query: str, top_k: int)`
    输出：`RAGRetrieveOutput(items: List[RAGDocument])`

    说明：
    - 使用 `RAG_RETRIEVE_SYSTEM_PROMPT` 作为系统提示词，维持接口一致性。
    - 若模型未配置（`get_model` 返回 None），直接返回提示词链（不进行结构化输出）。
    - 正常情况下，绑定结构化输出为 `RAGRetrieveOutput`，方便统一解析。
    """
    settings = get_settings()
    llm = get_model(settings)
    prompt = ChatPromptTemplate.from_messages([
        ("system", RAG_RETRIEVE_SYSTEM_PROMPT),
        ("human", "{query}"),
    ])
    if llm is None:
        return prompt
    # 绑定结构化输出：模型响应将按 `RAGRetrieveOutput` 解析
    structured_llm = llm.with_structured_output(RAGRetrieveOutput)
    chain = prompt | structured_llm
    return chain


def get_rag_rerank_agent() -> Runnable[RAGRerankInput, RAGRerankOutput]:
    """
    构建并返回一个“重排占位代理”。

    输入：`RAGRerankInput(query: str, items: List[RAGDocument])`
    输出：`RAGRerankOutput(items: List[RAGDocument])`

    说明：
    - 使用 `RAG_RERANK_SYSTEM_PROMPT` 作为系统提示词。
    - 若模型未配置，则返回提示词链；否则绑定结构化输出为 `RAGRerankOutput`。
    """
    settings = get_settings()
    llm = get_model(settings)
    prompt = ChatPromptTemplate.from_messages([
        ("system", RAG_RERANK_SYSTEM_PROMPT),
        ("human", "{query}"),
    ])
    if llm is None:
        return prompt
    # 绑定结构化输出：模型响应将按 `RAGRerankOutput` 解析
    structured_llm = llm.with_structured_output(RAGRerankOutput)
    chain = prompt | structured_llm
    return chain


def rag_retrieve(input_data: RAGRetrieveInput) -> RAGRetrieveOutput:
    """
    检索占位实现：返回空候选列表。

    适用场景：
    - 演示/占位：在真实检索逻辑（向量库/倒排索引等）未接入前，维持调用接口。
    - 单元测试：验证调用链路与数据结构，不依赖外部存储。
    """
    return RAGRetrieveOutput(items=[])


def rag_rerank(input_data: RAGRerankInput) -> RAGRerankOutput:
    """
    重排占位实现：为输入的候选文档生成一个可预测的占位分数，并原样返回。

    当前打分策略（占位）：
    - `score = len(query) - index`，其中 `index` 是候选的枚举序号。
    - 仅用于演示，不代表真实效果。
    """
    items: List[RAGDocument] = []
    for i, d in enumerate(input_data.items):
        items.append(
            RAGDocument(
                id=d.id,
                content=d.content,
                score=float(len(input_data.query)) - float(i),
                metadata=d.metadata,
            )
        )
    return RAGRerankOutput(items=items)