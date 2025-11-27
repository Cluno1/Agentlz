from __future__ import annotations

"""分块嵌入服务层

封装对 `chunk_embeddings` 的增删改查业务逻辑，复用仓储层操作；
当未显式提供向量时，基于内容文本自动生成嵌入向量。
"""

from typing import Any, Dict, List, Optional, Sequence

from agentlz.core.embedding_model_factory import get_hf_embeddings
from agentlz.repositories.chunk_embeddings_repository import (
    create_chunk_embedding as _create,
    get_chunk_embedding as _get,
    list_chunk_embeddings as _list,
    update_chunk_embedding as _update,
    delete_chunk_embedding as _delete,
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

# markdown 文本切割成小文本块
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
        # langchain 1.0+ 版本的导入
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownTextSplitter
            use_markdown_splitter = True
        except ImportError:
            # 如果新版导入失败，尝试旧版导入
            try:
                from langchain.text_splitter import RecursiveCharacterTextSplitter
                use_markdown_splitter = False
            except ImportError:
                # 再尝试旧版的text_splitters
                from langchain.text_splitters import RecursiveCharacterTextSplitter
                use_markdown_splitter = False
        
        if use_markdown_splitter:
            # 新版langchain的逻辑
            markdown_splitter = MarkdownTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separators=["\n\n", "\n", "。", "！", "？", "，", " ", ""]
            )
            
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separators=[
                    "\n\n",      # 段落
                    "\n",        # 换行
                    "。",        # 中文句号
                    "！",        # 中文感叹号
                    "？",        # 中文问号
                    "，",        # 中文逗号
                    " ",         # 空格
                    ""           # 字符级别
                ],
                length_function=len,
                is_separator_regex=False
            )
            
            # 先按Markdown结构切割，再按中文语义切割
            md_chunks = markdown_splitter.split_text(content)
            final_chunks = []

            for chunk in md_chunks:
                if len(chunk) > chunk_size:
                    # 如果Markdown块太大，进一步用递归切割器分割
                    sub_chunks = text_splitter.split_text(chunk)
                    final_chunks.extend(sub_chunks)
                else:
                    final_chunks.append(chunk)
            return final_chunks
        else:
            # langchain 1.0.2版本的逻辑 - 只用RecursiveCharacterTextSplitter
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separators=[
                    "\n\n",      # 段落
                    "\n",        # 换行
                    "#",         # Markdown标题
                    "##",
                    "###",
                    "####",
                    "。",        # 中文句号
                    "！",        # 中文感叹号
                    "？",        # 中文问号
                    "，",        # 中文逗号
                    " ",         # 空格
                    ""           # 字符级别
                ],
                length_function=len
            )
            
            # 直接使用RecursiveCharacterTextSplitter切割
            chunks = text_splitter.split_text(content)
            return chunks
            
    except ImportError as e:
        # 如果LangChain完全不可用，使用基础的中文切割
        print(f"LangChain导入失败: {e}，使用备用切割方案")
        return basic_chinese_text_split(content, chunk_size, chunk_overlap)
    except Exception as e:
        # 其他错误，使用备用方案
        print(f"LangChain切割失败: {e}，使用备用切割方案")
        return basic_chinese_text_split(content, chunk_size, chunk_overlap)

def basic_chinese_text_split(content: str, max_size: int = 500, overlap: int = 50) -> List[str]:
    """基础中文文本切割（备用方案）"""
    import re
    
    # 按中文句子结束符和Markdown结构分割
    sentences = re.split(r'([。！？\n]+|#{1,6}\s+)', content)
    
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