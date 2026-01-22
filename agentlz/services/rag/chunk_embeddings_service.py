from __future__ import annotations

from agentlz.core.logger import setup_logging

"""分块嵌入服务层

封装对 `chunk_embeddings` 的增删改查业务逻辑，复用仓储层操作；
当未显式提供向量时，基于内容文本自动生成嵌入向量。
"""

from typing import Any, Dict, List, Optional, Sequence, Literal

from agentlz.core.embedding_model_factory import get_hf_embeddings
from agentlz.repositories.chunk_embeddings_repository import (
    create_chunk_embedding as _create,
    get_chunk_embedding as _get,
    list_chunk_embeddings as _list,
    update_chunk_embedding as _update,
    delete_chunk_embedding as _delete,
    search_similar_chunks as _search_similar,
)


_EMB = None


def _get_embedder():
    """获取并缓存嵌入模型实例

    作用:
        - 懒加载并缓存 `HuggingFaceEmbeddings`，避免重复初始化带来的性能开销。

    返回值:
        - 嵌入模型对象，用于生成查询或文本的向量表示。

    异常:
        - 当环境缺失依赖或模型初始化失败时，底层工厂函数会抛出异常。
    """
    global _EMB
    if _EMB is None:
        _EMB = get_hf_embeddings()
    return _EMB


def embed_message_service(*, message: str) -> Sequence[float]:
    """将输入消息转换为嵌入向量

    参数:
        - message: 原始文本消息

    返回值:
        - 向量数组（Sequence[float]），用于相似度搜索或存储
    """
    if not isinstance(message, str) or message.strip() == "":
       return []
    return _get_embedder().embed_query(message)


def create_chunk_embedding_service(*, tenant_id: str, chunk_id: str, doc_id: str, content: Optional[str] = None, embedding: Optional[Sequence[float]] = None, chunk_index: int = 0, length: int = 0, strategy: str = "0") -> Dict[str, Any]:
    """创建分块嵌入记录

    行为:
        - 若显式提供 `embedding` 则直接写入；
        - 否则使用 `content` 文本生成向量后写入（需保证模型维度与表列维度一致）。

    参数:
        - tenant_id: 租户标识，用于行级安全隔离（RLS）。
        - chunk_id: 分块唯一ID，作为主键。
        - doc_id: 文档ID，便于筛选与关联。
        - content: 分块原文内容，可为空（当已提供 `embedding`）。
        - embedding: 预生成的向量；为空时将基于 `content` 自动生成。
        - chunk_index: 分块索引。
        - length: 分块长度。
        - strategy: 切割策略。

    返回值:
        - 新记录的字典表示（不包含向量），含 `chunk_id/doc_id/tenant_id/content/created_at`。

    异常:
        - ValueError: 当未提供 `embedding` 且 `content` 为空时。
    """
    vec: Sequence[float]
    if embedding is not None:
        vec = embedding
    else:
        if not content:
            raise ValueError("content_or_embedding_required")
        vec = _get_embedder().embed_query(str(content))
    return _create(tenant_id=tenant_id, chunk_id=chunk_id, doc_id=doc_id, embedding=vec, content=content, chunk_index=chunk_index, length=length, strategy=strategy)


def get_chunk_embedding_service(*, tenant_id: str, chunk_id: str, include_vector: bool = False) -> Optional[Dict[str, Any]]:
    """查询单条分块嵌入记录

    参数:
        - tenant_id: 租户标识，用于 RLS 隔离。
        - chunk_id: 分块主键ID。
        - include_vector: 是否返回向量（True 时返回 `embedding` 数组）。

    返回值:
        - 记录字典或 None；当 `include_vector=True` 时包含 `embedding` 字段。
    """
    return _get(tenant_id=tenant_id, chunk_id=chunk_id, include_vector=include_vector)

 
def list_chunk_embeddings_service(
    *,
    tenant_id: str,
    doc_id: Optional[str] = None,
    strategy: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    include_vector: bool = False
) -> List[Dict[str, Any]]:
    """分页查询分块嵌入列表（支持按 strategy 聚合）
    
    参数:
        - tenant_id: 租户标识，用于 RLS 隔离。
        - doc_id: 可选文档ID；为空则返回该租户范围内的多文档分块。
        - strategy: 可选切割策略；传入则仅返回该策略分组，未传入则返回所有策略分组。
        - limit: 每页数量上限。
        - offset: 偏移量，用于分页。
        - include_vector: 是否返回向量字段（仅用于透传，聚合结果不含 embedding）。
    
    返回值:
        - 当传入 `strategy` 时：[{文档信息..., "<strategy>": [{index, chunk_id, content, created_at, embedding?}]}]
        - 当未传入 `strategy` 时：[{文档信息..., "0":[...], "1":[...], ...}]（当 include_vector=True 时，分块项含 embedding）
        - 文档信息包含: doc_id, tenant_id
    """
    # 读取原始分块列表（仓储层已包含 chunk_index 与 strategy 字段）
    rows = _list(tenant_id=tenant_id, doc_id=doc_id, limit=limit, offset=offset, include_vector=include_vector)
    if not rows:
        return []
    
    grouped: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        # 文档与租户信息
        did = str(r.get("doc_id") or "")
        tid = str(r.get("tenant_id") or tenant_id)
        # 策略分组：优先使用外部传入的 strategy；未传入时使用记录中的 strategy
        s = strategy if strategy is not None else str(r.get("strategy") or "0")
        # 分块索引（保证顺序）
        idx = int(r.get("chunk_index") or 0)
        # 分块条目（不含向量）
        item = {
            "index": idx,
            "chunk_id": str(r.get("chunk_id") or ""),
            "content": r.get("content"),
            "created_at": r.get("created_at"),
        }
        # 当需要返回向量且底层已返回 embedding，则加入
        if include_vector and r.get("embedding") is not None:
            item["embedding"] = r.get("embedding")
        # 获取或创建当前文档的聚合桶
        doc_bucket = grouped.get(did)
        if doc_bucket is None:
            doc_bucket = {"doc_id": did, "tenant_id": tid}
            grouped[did] = doc_bucket
        # 追加到对应策略数组
        arr = doc_bucket.setdefault(s, [])
        arr.append(item)
    
    # 每个策略内按 index 排序，保证块顺序自然
    for _, doc_bucket in grouped.items():
        for k, v in list(doc_bucket.items()):
            if k in ("doc_id", "tenant_id"):
                continue
            try:
                v.sort(key=lambda x: int(x.get("index", 0)))
            except Exception:
                pass
    
    return list(grouped.values())


def update_chunk_embedding_service(*, tenant_id: str, chunk_id: str, content: Optional[str] = None, embedding: Optional[Sequence[float]] = None) -> Optional[Dict[str, Any]]:
    """更新分块嵌入或内容

    行为:
        - 若传入 `embedding` 则直接更新向量；
        - 若未传入 `embedding` 且提供了新的 `content`，则自动生成并更新向量；
        - 若两者均为空，仅返回当前记录（由仓储层决定）。

    参数:
        - tenant_id: 租户标识。
        - chunk_id: 分块主键ID。
        - content: 新的分块文本内容（可选）。
        - embedding: 新的向量（可选）。

    返回值:
        - 更新后的记录字典；不存在时返回 None。
    """
    vec: Optional[Sequence[float]] = embedding
    if vec is None and content is not None:
        vec = _get_embedder().embed_query(str(content))
    return _update(tenant_id=tenant_id, chunk_id=chunk_id, embedding=vec, content=content)


def delete_chunk_embedding_service(*, tenant_id: str, chunk_id: str) -> bool:
    """删除分块嵌入记录

    参数:
        - tenant_id: 租户标识。
        - chunk_id: 分块主键ID。

    返回值:
        - 删除成功返回 True；否则返回 False。
    """
    return _delete(tenant_id=tenant_id, chunk_id=chunk_id)


def search_similar_chunks_service(
    *,
    tenant_id: str,
    message:str,
    messages: Optional[Sequence[str]] = None,
    doc_id: Optional[str] = None,
    doc_ids: Optional[Sequence[str]] = None,
    distance_metric: Literal["euclidean", "cosine"] = "euclidean",
    limit: int = 10,
    include_vector: bool = False
) -> List[Dict[str, Any]]:
    """向量相似度搜索服务
    
    基于给定的embedding向量，使用指定的距离度量方式搜索最相似的文本块。
    支持欧几里得距离和余弦相似度两种度量方式。
    
    行为:
        - 调用repository层进行向量相似度搜索
        - 支持按文档ID过滤结果
        - 返回按相似度排序的结果列表
    
    参数:
        - tenant_id: 租户标识，用于RLS隔离
        - message: 查询消息，将自动向量化
        - messages: 可选的消息列表，将对每条消息分别检索并合并去重后返回全局 Top-K
        - doc_id: 可选的文档ID过滤条件，为空则搜索所有文档
        - distance_metric: 距离度量方式，可选"euclidean"或"cosine"
        - limit: 返回结果数量上限
        - include_vector: 是否返回向量字段
    
    返回值:
        - 相似文本块列表，按相似度升序排列（距离越小越相似）
        - 每个结果包含: chunk_id, doc_id, content, created_at, similarity_score
        - 当include_vector=True时额外包含embedding向量
        - 当传入 `messages` 时，将对每条消息分别检索并合并去重后返回全局 Top-K
    
    异常:
        - ValueError: 当distance_metric不是"euclidean"或"cosine"时
        - RuntimeError: 当向量维度不匹配或数据库查询失败时
    
    示例:
        >>> query_embedding = [0.1, 0.2, ..., 0.1536]  # 1536维向量
        >>> results = search_similar_chunks_service(
        ...     tenant_id="tenant_123",
        ...     embedding=query_embedding,
        ...     distance_metric="cosine",
        ...     limit=5
        ... )
        >>> for result in results:
        ...     print(f"相似度: {result['similarity_score']:.4f}")
        ...     print(f"内容: {result['content'][:100]}...")
    """
    if messages and len(messages) > 0:
        merged: List[Dict[str, Any]] = []
        best_by_chunk: Dict[str, Dict[str, Any]] = {}
        for msg in messages:
            if not isinstance(msg, str) or msg.strip() == "":
                continue
            vec = embed_message_service(message=msg)
            rows = _search_similar(
                tenant_id=tenant_id,
                embedding=vec,
                doc_id=doc_id,
                doc_ids=doc_ids,
                distance_metric=distance_metric,
                limit=limit,
                include_vector=include_vector,
            )
            for r in rows:
                cid = str(r.get("chunk_id") or "")
                score = float(r.get("similarity_score") or 1e9)
                prev = best_by_chunk.get(cid)
                if prev is None or float(prev.get("similarity_score") or 1e9) > score:
                    best_by_chunk[cid] = r
        if best_by_chunk:
            merged = list(best_by_chunk.values())
            merged.sort(key=lambda x: float(x.get("similarity_score") or 1e9))
            return merged[:limit]
        return []
    
    vec = embed_message_service(message=message)
    return _search_similar(
        tenant_id=tenant_id,
        embedding=vec,
        doc_id=doc_id,
        doc_ids=doc_ids,
        distance_metric=distance_metric,
        limit=limit,
        include_vector=include_vector,
    )


def split_markdown_into_chunks(content: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
    """将Markdown文本切割成适合向量化的块
    
    针对中文优化的智能切割策略：
    1. 优先保持Markdown结构完整性
    2. 按中文语义边界切割（句号、感叹号、问号）
    3. 控制块大小和重叠度
    
    Args:
        content: Markdown格式的文本内容
        chunk_size: 每块的最大字符数
        chunk_overlap: 块之间的重叠字符数
    
    Returns:
        List[str]: 文本块列表
    """
      
    try:      
        from langchain_text_splitters import RecursiveCharacterTextSplitter
            
        # 尝试新版本的参数格式
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=[
                "\n\n",      # 段落
                "\n",        # 换行
                "#",         # Markdown标题
                "##",        # Markdown二级标题
                "###",       # Markdown三级标题
                "####",      # Markdown四级标题
                "。",        # 中文句号
                "！",        # 中文感叹号
                "？",        # 中文问号
                "，",        # 中文逗号
                " ",         # 空格
                ""           # 字符级别
            ]
        )
    
        # 直接使用RecursiveCharacterTextSplitter切割
        chunks = text_splitter.split_text(content)
        return chunks
            
    except ImportError as e:
        # 如果LangChain完全不可用，使用基础的中文切割
        print(f"LangChain导入失败: {e}，使用备用切割方案")
        return basic_chinese_text_split(content, chunk_size, chunk_overlap)
   

def basic_chinese_text_split(content: str, max_size: int = 500, overlap: int = 50) -> List[str]:
    """基础中文文本切割（备用方案）"""
    import re
    
    # 按中文句子结束符和Markdown结构分割
    sentences = re.split(r'([。！？, .\n]+|#{1,6}\s+)', content)
    
    chunks = []
    current_chunk = ""
    
    for i in range(0, len(sentences), 2):
        if i < len(sentences):
            sentence = sentences[i]
            if i + 1 < len(sentences) and sentences[i + 1]:
                sentence += sentences[i + 1]
            
            if len(current_chunk) + len(sentence) <= max_size:
                current_chunk += sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    # 添加重叠部分
                    overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
                    current_chunk = overlap_text + sentence
                else:
                    # 如果单句就超过max_size，需要进一步切割
                    if len(sentence) > max_size:
                        # 按字符切割长句
                        for j in range(0, len(sentence), max_size - overlap):
                            chunk_part = sentence[j:j + max_size]
                            if j > 0:  # 添加重叠
                                chunk_part = sentence[max(0, j - overlap):j + max_size]
                            chunks.append(chunk_part.strip())
                        current_chunk = ""
                    else:
                        current_chunk = sentence
    
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    # 过滤空块
    return [chunk for chunk in chunks if chunk.strip()]


def chunk_fixed_length_boundary(content: str, target_length: int = 600, overlap: int = 80) -> List[str]:
    """改进的固定长度切片（边界感知）

    目标:
        - 以目标长度为上限，在接近长度阈值处优先选择自然语言边界（句号/问号/换行/标题）作为切点，避免句中断裂。

    输入:
        - content: Markdown格式文本
        - target_length: 目标分块长度，默认 600
        - overlap: 分块重叠长度，默认 80

    输出:
        - List[str]: 切片列表（带少量重叠）

    说明:
        - 仅依赖正则与中文标点；适合作为默认安全策略。
    """
    import re

    # 参数校验
    if not isinstance(content, str) or not content.strip():
        return []

    # 先按段落粗分（双换行优先）
    # 这一步是为了快速隔离大的语义块，避免一开始就陷入细节
    paragraphs = re.split(r"\n\n+", content)
    chunks: List[str] = []
    buf = ""

    def flush_buf():
        """将当前缓冲区内容作为分块输出，并保留重叠部分"""
        nonlocal buf
        if buf.strip():
            chunks.append(buf.strip())
            # 重叠片段（避免跨块信息丢失）
            # 取缓冲区末尾的 overlap 长度作为下一个块的起始
            ov = buf[-overlap:] if len(buf) > overlap else buf
            buf = ov

    for para in paragraphs:
        if not para.strip():
            continue
        # 二次按句子边界分割（保留分隔符）
        # 使用正则表达式捕获组 () 保留分隔符，方便后续重建句子
        parts = re.split(r"([。！？；;!?]\s*|\n+|#{1,6}\s+)", para)
        # 将句子和分隔符合并
        sentences: List[str] = []
        for i in range(0, len(parts), 2):
            s = parts[i] or ""
            if i + 1 < len(parts) and parts[i + 1]:
                s += parts[i + 1]
            if s:
                sentences.append(s)

        for s in sentences:
            # 如果加上当前句不超过目标长度，则加入缓冲区
            if len(buf) + len(s) <= target_length:
                buf += s
            else:
                # 接近阈值: 优先在当前句结束处切分，保证句子完整性
                flush_buf()
                # 如果单句太长，按字符强制切片
                if len(s) > target_length:
                    start = 0
                    step = target_length - overlap
                    while start < len(s):
                        end = min(start + target_length, len(s))
                        piece = s[start:end]
                        if start > 0:
                            # 强制切片时也保留重叠
                            piece = s[max(0, start - overlap):end]
                        chunks.append(piece.strip())
                        start += step
                    # 最后一个强制切片的末尾作为新的缓冲区
                    buf = chunks[-1][-overlap:] if chunks else ""
                else:
                    # 如果单句不算太长，直接作为新缓冲区的开始
                    buf = buf + s if not buf else s  

    # 处理剩余的缓冲区
    if buf.strip():
        chunks.append(buf.strip())

    return [c for c in chunks if c.strip()]


def chunk_semantic_similarity(
    content: str, 
    max_size: int = 800, 
    min_size: int = 200, 
    overlap: int = 100, 
    threshold: float = 0.35
) -> List[str]:
    """语义切片（Embedding 相似度驱动）

    目标:
        - 依据相邻句段的嵌入相似度或主题转折信号决定边界，保证语义完整。

    输入:
        - content: Markdown格式文本
        - max_size: 最大块长度，默认 800
        - min_size: 最小块长度，默认 200
        - overlap: 重叠长度，默认 100
        - threshold: 相似度阈值，低于此值触发切分，默认 0.35

    输出:
        - List[str]: 语义连续的文本块列表

    策略:
        - 按句子分割并计算相邻句子的余弦相似度；
        - 当相似度骤降或块长度超阈值时切分；
        - 适度重叠以保留跨句线索。
    """
    import re
    import math

    if not isinstance(content, str) or not content.strip():
        return []

    # 按标点和换行符分割句子
    parts = re.split(r"([。！？；;!?]\s*|\n+|#{1,6}\s+)", content)
    sentences: List[str] = []
    for i in range(0, len(parts), 2):
        s = parts[i] or ""
        if i + 1 < len(parts) and parts[i + 1]:
            s += parts[i + 1]
        if s.strip():
            sentences.append(s.strip())

    def cosine(u: Sequence[float], v: Sequence[float]) -> float:
        """计算两个向量的余弦相似度"""
        if not u or not v:
            return 0.0
        dot = sum((x * y) for x, y in zip(u, v))
        nu = math.sqrt(sum((x * x) for x in u))
        nv = math.sqrt(sum((y * y) for y in v))
        if nu == 0 or nv == 0:
            return 0.0
        return dot / (nu * nv)

    # 批量计算所有句子的嵌入向量
    # 注意：这可能会产生大量 API 调用，需注意性能和成本
    vecs: List[Sequence[float]] = [embed_message_service(message=s) for s in sentences]

    chunks: List[str] = []
    buf = ""
    last_vec: Optional[Sequence[float]] = None
    
    for idx, s in enumerate(sentences):
        v = vecs[idx]
        sim = cosine(last_vec or [], v)

        buf_len = len(buf)
        # 判断切分条件：
        # 1. 缓冲区已达到最小长度
        # 2. 并且 (加上当前句会超过最大长度 OR 与上一句相似度低于阈值)
        if buf_len >= min_size and (buf_len + len(s) > max_size or sim < threshold):
            # 触发切分
            if buf.strip():
                chunks.append(buf.strip())
                # 保留重叠部分
                ov = buf[-overlap:] if len(buf) > overlap else buf
                buf = ov + s
        else:
            # 合并到当前块
            buf += s
        last_vec = v

    # 处理剩余内容
    if buf.strip():
        chunks.append(buf.strip())

    return [c for c in chunks if c.strip()]


def chunk_llm_semantic(content: str, chunk_size: int = 800) -> List[str]:
    """LLM 语义切片（真实模型调用 + 安全回退）
    
    目标：
        - 基于大语言模型对 Markdown 文本进行“主题/任务/意图”驱动的智能分段；
        - 保持结构完整性（标题、代码块、列表、表格），在自然语言边界处截断；
        - 结合 chunk_size 控制片段长度，避免信息过载。
    
    输入：
        - content：Markdown 格式文本
        - chunk_size：单片段最大长度（字符数），默认 800
    
    返回值：
        - List[str]：语义片段数组；当模型不可用或调用失败时，回退为“标题/空行粗分 + 边界感知细分”的占位策略。
    
    实现说明：
        - 首选调用 agents.rag.chunk_semantic_agent 中的 LLM 代理（结构化输出为 segments）；
        - 当模型未配置或发生异常时，采用安全回退策略保证函数稳定性。
    """
    if not isinstance(content, str) or not content.strip():
        return []
    try:
        from agentlz.agents.rag.chunk_semantic_agent import get_chunk_semantic_agent
        agent = get_chunk_semantic_agent()
        # 若返回的是 Prompt（模型未配置），直接触发回退逻辑
        from langchain_core.prompts import ChatPromptTemplate  # type: ignore
        if isinstance(agent, ChatPromptTemplate):
            raise RuntimeError("llm_unavailable")
        resp = agent.invoke({"content": content, "chunk_size": int(chunk_size)})
        try:
            segs = getattr(resp, "segments", None)
            if isinstance(segs, list) and segs:
                return [s for s in segs if isinstance(s, str) and s.strip()]
        except Exception:
            pass
        # 若结构化解析失败，尝试将内容作为字符串解析
        text = getattr(resp, "content", str(resp))
        if isinstance(text, str) and text.strip():
            # 最后兜底：将整体文本作为单块返回
            return [text.strip()]
    except Exception:
        logger = setup_logging(__name__)
        logger.error("chunk_llm_semantic failed", exc_info=True)
        pass
    # 安全回退：标题/空行粗分 + 边界感知细分
    import re
    blocks = re.split(r"(\n{2,}|^#{1,6}\s+.*$)", content, flags=re.MULTILINE)
    merged: List[str] = []
    for i in range(0, len(blocks), 2):
        seg = blocks[i] or ""
        if i + 1 < len(blocks) and blocks[i + 1]:
            seg = (blocks[i + 1] or "") + ("\n" + seg if seg else "")
        if seg.strip():
            merged.append(seg.strip())
    final: List[str] = []
    for b in merged:
        if len(b) <= chunk_size:
            final.append(b)
        else:
            final.extend(chunk_fixed_length_boundary(b, target_length=chunk_size))
    return [c for c in final if c.strip()]


def chunk_hierarchical(content: str, target_length: int = 600, overlap: int = 80) -> List[str]:
    """层次切片（章节→段落→句子的小粒度组织）

    目标:
        - 先生成较大粒度块（章节/小节），再在块内生成细粒度子块；最终按层次顺序扁平化输出。

    输入:
        - content: Markdown格式文本
        - target_length: 细粒度分块的目标长度，默认 600
        - overlap: 细粒度分块的重叠长度，默认 80

    输出:
        - List[str]: 层次化但扁平输出的块列表
    """
    import re

    if not isinstance(content, str) or not content.strip():
        return []

    # 识别标题层级，优先 H1/H2/H3
    pattern = re.compile(r"^#{1,3}\s+.*$", flags=re.MULTILINE)
    indices = [m.start() for m in pattern.finditer(content)]
    indices = [0] + indices + [len(content)]

    coarse_blocks: List[str] = []
    for i in range(len(indices) - 1):
        block = content[indices[i]:indices[i + 1]].strip()
        if block:
            coarse_blocks.append(block)

    final: List[str] = []
    for b in coarse_blocks:
        # 块内再做边界感知细分
        final.extend(chunk_fixed_length_boundary(b, target_length=target_length, overlap=overlap))

    return [c for c in final if c.strip()]


def chunk_sliding_window(content: str, window_size: int = 600, overlap: int = 220) -> List[str]:
    """滑动窗口切片（高重叠上下文）

    目标:
        - 使用固定长度窗口与重叠，保证跨块信息连续，适合代码/公式/规范类文本。

    输入:
        - content: Markdown格式文本
        - window_size: 窗口长度，默认 600
        - overlap: 重叠长度，默认 220

    输出:
        - List[str]: 切片列表
    """
    if not isinstance(content, str) or not content.strip():
        return []

    # 计算步长
    step = max(1, window_size - overlap)

    chunks: List[str] = []
    start = 0
    n = len(content)
    
    while start < n:
        end = min(start + window_size, n)
        piece = content[start:end]
        
        # 尽量在换行处结束，提升可读性
        if end < n:
            back = piece.rfind("\n")
            # 如果回退距离不过大，则优先在换行处截断
            if back > 0 and (end - start - back) < 80:
                end = start + back
                piece = content[start:end]
        
        chunks.append(piece.strip())
        start = min(start + step, n)
        
    return [c for c in chunks if c.strip()]


def chunk_structure_aware(content: str, max_size: int = 800) -> List[str]:
    """结构感知切片（Markdown/代码块/列表/表格）

    目标:
        - 保持Markdown结构完整性：标题段、代码块、列表、表格等尽量不被拆散；
        - 适配混排文档，提高后续检索的结构一致性。

    输入:
        - content: Markdown格式文本
        - max_size: 普通文本块的最大长度，默认 800

    输出:
        - List[str]: 切片列表
    """
    if not isinstance(content, str) or not content.strip():
        return []

    lines = content.splitlines()
    chunks: List[str] = []
    buf: List[str] = []
    in_code = False

    for line in lines:
        # 代码块（fenced code）优先完整保留
        if line.strip().startswith("```"):
            if in_code:
                buf.append(line)
                chunks.append("\n".join(buf).strip())
                buf = []
                in_code = False
            else:
                if buf:
                    # 代码块前的缓冲作为一个块输出
                    chunks.extend(chunk_fixed_length_boundary("\n".join(buf), target_length=max_size))
                    buf = []
                buf.append(line)
                in_code = True
            continue

        if in_code:
            buf.append(line)
            continue

        # 表格或列表区域尽量整体保留
        if line.strip().startswith("|") or line.strip().startswith("-") or line.strip().startswith("*"):
            buf.append(line)
            continue

        # 普通文本行
        buf.append(line)
        # 到达较长后切分输出
        if len("\n".join(buf)) > max_size:
            chunks.extend(chunk_fixed_length_boundary("\n".join(buf), target_length=max_size))
            buf = []

    if buf:
        chunks.extend(chunk_fixed_length_boundary("\n".join(buf), target_length=max_size))

    return [c for c in chunks if c.strip()]


def chunk_dynamic_adaptive(content: str, base_chunk_size: int = 700, overlap: int = 80) -> List[str]:
    """动态自适应切片（启发式策略）
    
    背景与动机:
        - 文档不同区域的信息密度差异较大（如规范中的定义段与示例段），固定长度切片可能导致某些块信息过载或过稀。
        - 本策略根据“标点密度”（近似衡量语义断点与信息密度）对块长度进行自适应调整：
          密集区域缩短块、稀疏区域适度放宽，以提升后续检索与召回的稳定性。
    
    参数:
        - content: Markdown 格式文本；会按行预分组以降低计算复杂度
        - base_chunk_size: 基础切片长度（字符数）；作为自适应的基线
        - overlap: 块间重叠长度；用于保留跨块线索，降低分割造成的信息丢失
    
    返回值:
        - List[str]: 切片列表；已进行空白清洗
    
    适用场景:
        - 技术文档、规范、教程等存在不同密度段落的混排文本
        - 希望在不引入昂贵模型计算的前提下，获得相对均衡的信息分布
    
    算法流程概要:
        1) 对文本按行进行粗分组（每组约 8 行），控制局部范围；
        2) 计算分组的标点密度（逗号/句号等占比），作为密度代理；
        3) 若密度超过阈值，则采用较短的“边界感知”切片；否则采用较长的 Markdown 递归切片；
        4) 对输出进行清洗、去空与重叠控制（交由被调用的具体切片器处理）。
    
    性能与注意事项:
        - 阈值 0.02 为经验值，针对中文语料；可根据数据集调参。
        - 该方法不计算嵌入，成本低；如需更强语义效果，结合 chunk_semantic_similarity。
    """
    if not isinstance(content, str) or not content.strip():
        return []

    import re

    # 预清洗：去除空行，按行处理更易捕捉结构
    lines = [ln for ln in content.splitlines() if ln.strip()]
    groups: List[str] = []
    cur: List[str] = []
    
    # 将文本按固定行数分组（近似段落），控制计算窗口大小
    for ln in lines:
        cur.append(ln)
        if len(cur) >= 8:
            groups.append("\n".join(cur))
            cur = []
    if cur:
        groups.append("\n".join(cur))

    out: List[str] = []
    for g in groups:
        # 标点密度估计：标点数量 / 文本长度
        punct = len(re.findall(r"[，。；；、!?]", g))
        density = punct / max(1, len(g))
        
        # 动态目标长度选择：密集段采用更短、更边界友好的切片；稀疏段采用递归字符切片
        if density > 0.02:
            # 信息密集：缩短目标长度（避免过载），保持一定下限
            out.extend(chunk_fixed_length_boundary(g, target_length=max(100, base_chunk_size - 100), overlap=overlap))
        else:
            # 信息稀疏：拉长（轻度放宽），递归分隔以保持结构
            out.extend(split_markdown_into_chunks(g, chunk_size=base_chunk_size, chunk_overlap=overlap))

    return [c for c in out if c.strip()]


def chunk_with_relations(content: str, max_size: int = 700) -> List[str]:
    """跨块关系与知识联结（占位实现）

    目标:
        - 在切片时尽量将存在引用/链接/同主题线索的句段合并，减少跨块分裂；
        - 通过检测 Markdown 链接、引用词、标题关联等，进行就近合并与增量重叠。

    输入:
        - content: Markdown格式文本
        - max_size: 合并后的最大长度，默认 700

    输出:
        - List[str]: 切片列表

    说明:
        - 仅返回字符串列表；若需图结构或元数据，请在此函数基础上扩展。
    """
    import re

    if not isinstance(content, str) or not content.strip():
        return []

    # 先按句子粗分
    parts = re.split(r"([。！？；;!?]\s*|\n+|#{1,6}\s+)", content)
    sentences: List[str] = []
    for i in range(0, len(parts), 2):
        s = parts[i] or ""
        if i + 1 < len(parts) and parts[i + 1]:
            s += parts[i + 1]
        if s.strip():
            sentences.append(s.strip())

    # 标记“关系加强”的句子（含链接/引用/参见/see also）
    def is_anchor(text: str) -> bool:
        return bool(re.search(r"\[[^\]]+\]\([^\)]+\)|参见|引用|see also|参考", text, flags=re.IGNORECASE))

    chunks: List[str] = []
    buf: List[str] = []
    
    for i, s in enumerate(sentences):
        buf.append(s)
        long_enough = sum(len(x) for x in buf) > max_size
        anchor_here = is_anchor(s)
        next_anchor = i + 1 < len(sentences) and is_anchor(sentences[i + 1])

        if long_enough or anchor_here or next_anchor:
            # 带关系的句段向前/向后各并入一条，增强上下文联结
            prev = sentences[i - 1] if i - 1 >= 0 else ""
            nxt = sentences[i + 1] if i + 1 < len(sentences) else ""
            
            # 合并上下文
            block = (prev + "" if prev else "") + "".join(buf) + (nxt if nxt else "")
            
            # 再次使用固定长度切片确保不超长
            for piece in chunk_fixed_length_boundary(block, target_length=max_size):
                chunks.append(piece)
            buf = []

    if buf:
        for piece in chunk_fixed_length_boundary("".join(buf), target_length=max_size):
            chunks.append(piece)

    # 去重与清洗
    seen = set()
    dedup: List[str] = []
    for c in chunks:
        key = c.strip()
        if key and key not in seen:
            dedup.append(key)
            seen.add(key)
    return dedup

def chunk_content_by_strategy(content: str, strategy: int = 0, meta: Optional[Dict[str, Any]] = None) -> List[str]:
    """统一切片入口（策略选择 + 参数绑定）
    
    用途:
        - 将本模块内所有可用切片方法集中到一个选择器中，通过 strategy 编号选择具体策略；
        - 通过 meta 绑定各策略的参数，避免接口膨胀，提升可扩展性与易用性。
    
    输入:
        - content: 待切割的 Markdown 文本
        - strategy: 整数策略编号（详见下方映射）
            0: basic_chinese_text_split（基础中文切割）
            1: split_markdown_into_chunks（递归字符切割，结构感知）
            2: chunk_fixed_length_boundary（固定长度 + 边界感知）
            3: chunk_semantic_similarity（语义相似度驱动切分）
            4: chunk_llm_semantic（LLM 语义分段，占位实现）
            5: chunk_hierarchical（章节→段落→句子层次切片）
            6: chunk_sliding_window（滑动窗口，高重叠上下文）
            7: chunk_structure_aware（结构感知：代码块/列表/表格）
            8: chunk_dynamic_adaptive（动态自适应：密度驱动）
            9: chunk_with_relations（跨块关系与联结）
        - meta: 参数绑定字典，不同策略支持的键：
            - 基础/边界/层次等：max_size、target_length、overlap
            - 递归分割：chunk_size、chunk_overlap
            - 语义相似度：max_size、min_size、overlap、threshold
            - 滑动窗口：window_size、overlap
            - LLM 分段：chunk_size
            - 动态自适应：base_chunk_size、overlap
    
    返回值:
        - List[str]: 切割后的块列表；默认保证非空清洗与合理重叠
    
    兼容性:
        - 当 meta 未提供或类型不正确时，自动回退到安全默认值；
        - strategy 非法时回退到基础切割（策略 0）。
    """
    if meta is None:
        meta = {}
    try:
        strategy_int = int(strategy)
    except (ValueError, TypeError):
        strategy_int = 0

    if strategy_int == 0:
        # 基础中文切割：适合无外部依赖的默认策略
        max_size = int(meta.get("max_size", 500) or 500)
        overlap = int(meta.get("overlap", 50) or 50)
        return basic_chinese_text_split(content, max_size=max_size, overlap=overlap)
    elif strategy_int == 1:
        # 递归字符切割（结构感知）：优先保持 Markdown 结构
        chunk_size = int(meta.get("chunk_size", 500) or 500)
        chunk_overlap = int(meta.get("chunk_overlap", 50) or 50)
        return split_markdown_into_chunks(content, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    elif strategy_int == 2:
        # 固定长度 + 边界感知：在句末/换行优先切分
        target_length = int(meta.get("target_length", 600) or 600)
        overlap = int(meta.get("overlap", 80) or 80)
        return chunk_fixed_length_boundary(content, target_length=target_length, overlap=overlap)
    elif strategy_int == 3:
        # 语义相似度驱动：计算相邻句的嵌入余弦相似度决定边界
        max_size = int(meta.get("max_size", 800) or 800)
        min_size = int(meta.get("min_size", 200) or 200)
        overlap = int(meta.get("overlap", 100) or 100)
        threshold = float(meta.get("threshold", 0.35) or 0.35)
        return chunk_semantic_similarity(content, max_size=max_size, min_size=min_size, overlap=overlap, threshold=threshold)
    elif strategy_int == 4:
        # LLM 语义分段（占位）：标题/空行粗分 + 边界感知细分
        chunk_size = int(meta.get("chunk_size", 800) or 800)
        return chunk_llm_semantic(content, chunk_size=chunk_size)
    elif strategy_int == 5:
        # 层次切片：按标题层级粗分，再进行边界感知细分
        target_length = int(meta.get("target_length", 600) or 600)
        overlap = int(meta.get("overlap", 80) or 80)
        return chunk_hierarchical(content, target_length=target_length, overlap=overlap)
    elif strategy_int == 6:
        # 滑动窗口：固定窗口 + 高重叠，适合代码/规范等连续文本
        window_size = int(meta.get("window_size", 600) or 600)
        overlap = int(meta.get("overlap", 220) or 220)
        return chunk_sliding_window(content, window_size=window_size, overlap=overlap)
    elif strategy_int == 7:
        # 结构感知：优先保留代码块/列表/表格等结构完整性
        max_size = int(meta.get("max_size", 800) or 800)
        return chunk_structure_aware(content, max_size=max_size)
    elif strategy_int == 8:
        # 动态自适应：基于标点密度自适应选择策略
        base_chunk_size = int(meta.get("base_chunk_size", 700) or 700)
        overlap = int(meta.get("overlap", 80) or 80)
        return chunk_dynamic_adaptive(content, base_chunk_size=base_chunk_size, overlap=overlap)
    elif strategy_int == 9:
        # 关系联结：考虑引用/链接等跨块关系进行就近合并
        max_size = int(meta.get("max_size", 700) or 700)
        return chunk_with_relations(content, max_size=max_size)
    else:
        # 非法策略编号：回退到基础中文切割
        max_size = int(meta.get("max_size", 500) or 500)
        overlap = int(meta.get("overlap", 50) or 50)
        return basic_chinese_text_split(content, max_size=max_size, overlap=overlap)
