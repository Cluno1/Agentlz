from __future__ import annotations

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


def create_chunk_embedding_service(*, tenant_id: str, chunk_id: str, doc_id: str, content: Optional[str] = None, embedding: Optional[Sequence[float]] = None) -> Dict[str, Any]:
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
    return _create(tenant_id=tenant_id, chunk_id=chunk_id, doc_id=doc_id, embedding=vec, content=content)


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


def list_chunk_embeddings_service(*, tenant_id: str, doc_id: Optional[str] = None, limit: int = 20, offset: int = 0, include_vector: bool = False) -> List[Dict[str, Any]]:
    """分页查询分块嵌入列表

    参数:
        - tenant_id: 租户标识，用于 RLS 隔离。
        - doc_id: 可选的文档ID过滤条件；为空则返回该租户所有分块。
        - limit: 每页数量上限。
        - offset: 偏移量，用于分页。
        - include_vector: 是否返回向量字段。

    返回值:
        - 记录字典列表；当 `include_vector=True` 时每条含 `embedding` 数组。
    """
    return _list(tenant_id=tenant_id, doc_id=doc_id, limit=limit, offset=offset, include_vector=include_vector)


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


def chunk_fixed_length_boundary(content: str) -> List[str]:
    """改进的固定长度切片（边界感知）

    目标:
        - 以目标长度为上限，在接近长度阈值处优先选择自然语言边界（句号/问号/换行/标题）作为切点，避免句中断裂。

    输入:
        - content: Markdown格式文本

    输出:
        - List[str]: 切片列表（带少量重叠）

    说明:
        - 仅依赖正则与中文标点；适合作为默认安全策略。
    """
    import re

    TARGET = 600
    OVERLAP = 80

    if not isinstance(content, str) or not content.strip():
        return []

    # 先按段落粗分（双换行优先）
    paragraphs = re.split(r"\n\n+", content)
    chunks: List[str] = []
    buf = ""

    def flush_buf():
        nonlocal buf
        if buf.strip():
            chunks.append(buf.strip())
            # 重叠片段（避免跨块信息丢失）
            ov = buf[-OVERLAP:] if len(buf) > OVERLAP else buf
            buf = ov

    for para in paragraphs:
        if not para.strip():
            continue
        # 二次按句子边界分割（保留分隔符）
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
            if len(buf) + len(s) <= TARGET:
                buf += s
            else:
                # 接近阈值: 优先在当前句结束处切分
                flush_buf()
                # 如果单句太长，按字符切片
                if len(s) > TARGET:
                    start = 0
                    step = TARGET - OVERLAP
                    while start < len(s):
                        end = min(start + TARGET, len(s))
                        piece = s[start:end]
                        if start > 0:
                            piece = s[max(0, start - OVERLAP):end]
                        chunks.append(piece.strip())
                        start += step
                    buf = chunks[-1][-OVERLAP:] if chunks else ""
                else:
                    buf = buf + s if not buf else s  # 使用当前句作为新的起始

    if buf.strip():
        chunks.append(buf.strip())

    return [c for c in chunks if c.strip()]


def chunk_semantic_similarity(content: str) -> List[str]:
    """语义切片（Embedding 相似度驱动）

    目标:
        - 依据相邻句段的嵌入相似度或主题转折信号决定边界，保证语义完整。

    输入:
        - content: Markdown格式文本

    输出:
        - List[str]: 语义连续的文本块列表

    策略:
        - 按句子分割并计算相邻句子的余弦相似度；
        - 当相似度骤降或块长度超阈值时切分；
        - 适度重叠以保留跨句线索。
    """
    import re
    import math

    MAX_SIZE = 800
    MIN_SIZE = 200
    OVERLAP = 100
    DROP_THRESHOLD = 0.35  # 相似度低于此阈值触发新块

    if not isinstance(content, str) or not content.strip():
        return []

    parts = re.split(r"([。！？；;!?]\s*|\n+|#{1,6}\s+)", content)
    sentences: List[str] = []
    for i in range(0, len(parts), 2):
        s = parts[i] or ""
        if i + 1 < len(parts) and parts[i + 1]:
            s += parts[i + 1]
        if s.strip():
            sentences.append(s.strip())

    def cosine(u: Sequence[float], v: Sequence[float]) -> float:
        if not u or not v:
            return 0.0
        dot = sum((x * y) for x, y in zip(u, v))
        nu = math.sqrt(sum((x * x) for x in u))
        nv = math.sqrt(sum((y * y) for y in v))
        if nu == 0 or nv == 0:
            return 0.0
        return dot / (nu * nv)

    # 计算句向量
    vecs: List[Sequence[float]] = [embed_message_service(message=s) for s in sentences]

    chunks: List[str] = []
    buf = ""
    last_vec: Optional[Sequence[float]] = None
    for idx, s in enumerate(sentences):
        v = vecs[idx]
        sim = cosine(last_vec or [], v)

        buf_len = len(buf)
        if buf_len >= MIN_SIZE and (buf_len + len(s) > MAX_SIZE or sim < DROP_THRESHOLD):
            # 到达长度或相似度骤降，触发切分
            if buf.strip():
                chunks.append(buf.strip())
                ov = buf[-OVERLAP:] if len(buf) > OVERLAP else buf
                buf = ov + s
        else:
            buf += s
        last_vec = v

    if buf.strip():
        chunks.append(buf.strip())

    return [c for c in chunks if c.strip()]


def chunk_llm_semantic(content: str) -> List[str]:
    """LLM 语义切片（模型辅助分割，占位实现）

    目标:
        - 按“主题/任务/意图”对文本进行智能分段，产出语义标签化的块。

    说明:
        - 本函数保留 LLM 调用占位，默认退化为结构感知 + 固定长度的组合策略；
        - 如需使用真实 LLM，请在占位函数 `_llm_segment_markdown` 中补充调用与解析逻辑。
    """
    import re

    if not isinstance(content, str) or not content.strip():
        return []

    def _llm_segment_markdown(md: str) -> List[str]:
        """占位: 调用 LLM 生成语义段落（请自行补充实际调用）。

        当前行为:
            - 优先按标题与空行分段；
            - 对超长段再用 `chunk_fixed_length_boundary` 细分。
        """
        # 标题/空行粗分
        blocks = re.split(r"(\n{2,}|^#{1,6}\s+.*$)", md, flags=re.MULTILINE)
        merged: List[str] = []
        cur = ""
        for i in range(0, len(blocks), 2):
            seg = blocks[i] or ""
            if i + 1 < len(blocks) and blocks[i + 1]:
                seg = (blocks[i + 1] or "") + ("\n" + seg if seg else "")
            if seg.strip():
                merged.append(seg.strip())
        # 返回粗分结果（后续细分）
        return merged

    coarse = _llm_segment_markdown(content)
    final: List[str] = []
    for b in coarse:
        if len(b) <= 800:
            final.append(b)
        else:
            final.extend(chunk_fixed_length_boundary(b))
    return [c for c in final if c.strip()]


def chunk_hierarchical(content: str) -> List[str]:
    """层次切片（章节→段落→句子的小粒度组织）

    目标:
        - 先生成较大粒度块（章节/小节），再在块内生成细粒度子块；最终按层次顺序扁平化输出。

    输入:
        - content: Markdown格式文本
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
        final.extend(chunk_fixed_length_boundary(b))

    return [c for c in final if c.strip()]


def chunk_sliding_window(content: str) -> List[str]:
    """滑动窗口切片（高重叠上下文）

    目标:
        - 使用固定长度窗口与重叠，保证跨块信息连续，适合代码/公式/规范类文本。

    输入/输出:
        - 输入 Markdown 文本，仅返回字符串列表。
    """
    if not isinstance(content, str) or not content.strip():
        return []

    WINDOW = 600
    STEP = 380  # 重叠约 220

    chunks: List[str] = []
    start = 0
    n = len(content)
    while start < n:
        end = min(start + WINDOW, n)
        piece = content[start:end]
        # 尽量在换行处结束，提升可读性
        if end < n:
            back = piece.rfind("\n")
            if back > 0 and (end - start - back) < 80:
                end = start + back
                piece = content[start:end]
        chunks.append(piece.strip())
        start = min(start + STEP, n)
    return [c for c in chunks if c.strip()]


def chunk_structure_aware(content: str) -> List[str]:
    """结构感知切片（Markdown/代码块/列表/表格）

    目标:
        - 保持Markdown结构完整性：标题段、代码块、列表、表格等尽量不被拆散；
        - 适配混排文档，提高后续检索的结构一致性。
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
                    chunks.extend(chunk_fixed_length_boundary("\n".join(buf)))
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
        if sum(len(l) for l in buf) > 800:
            chunks.extend(chunk_fixed_length_boundary("\n".join(buf)))
            buf = []

    if buf:
        chunks.extend(chunk_fixed_length_boundary("\n".join(buf)))

    return [c for c in chunks if c.strip()]


def chunk_dynamic_adaptive(content: str) -> List[str]:
    """动态自适应切片（基于密度/困惑度的启发式占位）

    目标:
        - 信息密集段落适当缩短块，稀疏段落适当拉长，控制“信息每块单位”均衡；
        - 依据标点密度与行长度的简单启发式进行自适应。
    """
    if not isinstance(content, str) or not content.strip():
        return []

    import re

    lines = [ln for ln in content.splitlines() if ln.strip()]
    groups: List[str] = []
    cur: List[str] = []
    for ln in lines:
        cur.append(ln)
        if len(cur) >= 8:
            groups.append("\n".join(cur))
            cur = []
    if cur:
        groups.append("\n".join(cur))

    out: List[str] = []
    for g in groups:
        # 标点密度估计（作为信息密度的代理）
        punct = len(re.findall(r"[，。；；、!?]", g))
        density = punct / max(1, len(g))
        # 动态目标长度
        if density > 0.02:
            # 信息密集：缩短
            out.extend(chunk_fixed_length_boundary(g))
        else:
            # 信息稀疏：拉长（轻度放宽）
            out.extend(split_markdown_into_chunks(g, chunk_size=700, chunk_overlap=80))

    return [c for c in out if c.strip()]


def chunk_with_relations(content: str) -> List[str]:
    """跨块关系与知识联结（占位实现）

    目标:
        - 在切片时尽量将存在引用/链接/同主题线索的句段合并，减少跨块分裂；
        - 通过检测 Markdown 链接、引用词、标题关联等，进行就近合并与增量重叠。

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
        long_enough = sum(len(x) for x in buf) > 700
        anchor_here = is_anchor(s)
        next_anchor = i + 1 < len(sentences) and is_anchor(sentences[i + 1])

        if long_enough or anchor_here or next_anchor:
            # 带关系的句段向前/向后各并入一条，增强上下文联结
            prev = sentences[i - 1] if i - 1 >= 0 else ""
            nxt = sentences[i + 1] if i + 1 < len(sentences) else ""
            block = (prev + "" if prev else "") + "".join(buf) + (nxt if nxt else "")
            for piece in chunk_fixed_length_boundary(block):
                chunks.append(piece)
            buf = []

    if buf:
        for piece in chunk_fixed_length_boundary("".join(buf)):
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