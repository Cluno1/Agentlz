"""
RAG 代理（占位实现）

本文件提供检索（Retrieve）的占位实现：
- 按查询语句召回候选文档；当前仅返回空列表作为演示。

设计意图
- 保持与实际 RAG 流程一致的接口形态（输入/输出 Schema、代理构造方式）。
- 便于后续替换为真实的向量检索逻辑（如 pgvector/faiss + 嵌入模型）。

使用方式
- 直接函数：`rag_retrieve(...)` 适合在代码中同步调用。
- 代理（LCEL 链）：`get_rag_retrieve_agent()` 返回可 `invoke` 的链，
  与其他 Agent 保持一致的调用体验，便于统一编排。
"""

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from agentlz.core.model_factory import get_model
from agentlz.config.settings import get_settings
from agentlz.schemas.rag import (
    RAGDocument,
    RAGRetrieveInput,
    RAGRetrieveOutput,
    RAGQueryInput,
    RAGQueryOutput,
)
from agentlz.prompts.rag.rag import (
    RAG_RETRIEVE_SYSTEM_PROMPT,
    RAG_QUERY_SYSTEM_PROMPT,
    RAG_ANSWER_SYSTEM_PROMPT,
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
    llm = get_model(settings=settings,streaming=True)
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


def rag_retrieve(input_data: RAGRetrieveInput) -> RAGRetrieveOutput:
    """
    检索占位实现：返回空候选列表。

    适用场景：
    - 演示/占位：在真实检索逻辑（向量库/倒排索引等）未接入前，维持调用接口。
    - 单元测试：验证调用链路与数据结构，不依赖外部存储。
    """
    return RAGRetrieveOutput(items=[])


def get_rag_query_agent(llm_override: object = None) -> Runnable[RAGQueryInput, RAGQueryOutput]:
    """
    构建并返回一个“查询占位代理”。

    输入：`RAGQueryInput(message: str, max_items: int = 6)`
    输出：`RAGQueryOutput(messages: List[str])`

    说明：
    - 使用 `RAG_QUERY_SYSTEM_PROMPT` 作为系统提示词，维持接口一致性。
    - 若模型未配置（`get_model` 返回 None），直接返回提示词链（不进行结构化输出）。
    - 正常情况下，绑定结构化输出为 `RAGQueryOutput`，方便统一解析。
    """
    settings = get_settings()
    llm = llm_override if llm_override is not None else get_model(settings=settings)
    prompt = ChatPromptTemplate.from_messages([
        ("system", RAG_QUERY_SYSTEM_PROMPT),
        ("human", "历史记录（可选）：\n<history>{history}</history>\n当前问题：\n<current_query>{message}</current_query>"),
    ])
    if llm is None:
        return prompt
    structured_llm = llm.with_structured_output(RAGQueryOutput)
    chain = prompt | structured_llm
    return chain


def rag_build_queries(input_data: RAGQueryInput) -> RAGQueryOutput:
    """
    从用户消息中提取查询短句。

    输入：`RAGQueryInput(message: str, max_items: int = 6)`
    输出：`RAGQueryOutput(messages: List[str])`

    说明：
    - 基于 `RAG_QUERY_SYSTEM_PROMPT` 提取查询短句，风格简洁、具体。
    - 避免泛化，优先保留专有名词、版本号、产品/接口名、错误码、文件/函数/类名等。
    - 最多返回 `max_items` 个查询短句，默认 6 个。
    """
    text = (input_data.message or "").strip()
    if text == "":
        return RAGQueryOutput(messages=[])
    seps = ["\n", "。", "！", "!", "？", "?", "，", ",", ";", "；", " "]
    parts: list[str] = [text]
    for s in seps:
        tmp: list[str] = []
        for p in parts:
            tmp.extend([x.strip() for x in p.split(s) if isinstance(x, str)])
        parts = tmp
    cleaned: list[str] = []
    seen = set()
    stop = {"的", "了", "和", "与", "及", "在", "是", "有", "并", "或"}
    for p in parts:
        if not p:
            continue
        cp = p.strip().strip("'\"()[]{}<>:：")
        if len(cp) < 2:
            continue
        if cp in stop:
            continue
        if cp not in seen:
            seen.add(cp)
            cleaned.append(cp)
    if text not in seen:
        cleaned.insert(0, text)
    if len(cleaned) > input_data.max_items:
        cleaned = cleaned[: input_data.max_items]
    return RAGQueryOutput(messages=cleaned)


def get_rag_answer_agent() -> Runnable:
    settings = get_settings()
    llm = get_model(settings=settings)
    prompt = ChatPromptTemplate.from_messages([
        ("system", RAG_ANSWER_SYSTEM_PROMPT),
        ("human", "用户问题：{message}\n候选文档：\n{doc}\n历史上下文：\n{history}"),
    ])
    if llm is None:
        return prompt
    return prompt | llm


def rag_answer(input_data: dict) -> str:
    msg = str(input_data.get("message") or "")
    doc = str(input_data.get("doc") or "")
    his = str(input_data.get("history") or "")
    agent = get_rag_answer_agent()
    if isinstance(agent, ChatPromptTemplate):
        return msg if msg else (doc[:2000] if doc else "模型未配置")
    try:
        resp = agent.invoke({"message": msg, "doc": doc, "history": his})
    except Exception:
        if msg:
            return msg
        if doc:
            return doc[:2000]
        return "服务暂时不可用，请稍后重试"
    try:
        return getattr(resp, "content", str(resp))
    except Exception:
        return str(resp)
