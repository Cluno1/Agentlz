from __future__ import annotations

"""
FAISS 向量数据库服务封装

提供针对 LangChain FAISS 的统一 CRUD 封装，包含：
- 索引加载/创建
- 批量写入文本（add_texts）
- 删除（delete）
- 单条读取（get_by_id）
- 相似度检索（similarity_search）
- 更新（update_text）

所有函数均采用中文文档说明，符合项目开发规范。
"""

import os
from typing import Any, Dict, List, Optional

try:
    from langchain_community.vectorstores import FAISS
except Exception:  # 兼容旧版本
    from langchain.vectorstores import FAISS  # type: ignore


class FAISSVectorService:
    """FAISS 向量数据库服务

    负责 FAISS 索引的加载、保存与常见 CRUD 操作封装。

    参数:
        persist_dir: 索引持久化目录。
        index_name: 索引名称（用于本地文件名）。
    """

    def __init__(self, persist_dir: str, index_name: str) -> None:
        self.persist_dir = persist_dir
        self.index_name = index_name

    def _index_path(self) -> str:
        """返回 FAISS 索引文件路径。"""
        return os.path.join(self.persist_dir, f"{self.index_name}.faiss")

    def load_or_create(self, embeddings) -> Optional[FAISS]:
        """加载现有索引，若不存在则返回 None（延迟创建）。

        参数:
            embeddings: 向量嵌入模型实例（LangChain Embeddings）。

        返回:
            已加载的 FAISS 向量库对象，或 None 表示尚未创建。
        """
        if os.path.exists(self._index_path()):
            return FAISS.load_local(
                self.persist_dir,
                embeddings=embeddings,
                index_name=self.index_name,
                allow_dangerous_deserialization=True,
            )
        return None

    def save(self, vectorstore: FAISS) -> None:
        """保存索引到持久化目录。"""
        vectorstore.save_local(self.persist_dir, index_name=self.index_name)

    def add_texts(
        self,
        vectorstore: Optional[FAISS],
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
        embeddings=None,
    ) -> FAISS:
        """批量添加文本到索引，支持懒创建。

        参数:
            vectorstore: 现有向量库对象；若为 None 则创建新索引。
            texts: 文本列表。
            metadatas: 元数据列表（可选）。
            ids: 文档 ID 列表（可选，建议提供以便 CRUD）。
            embeddings: 当 vectorstore 为 None 时，用于创建新索引的嵌入模型。

        返回:
            更新后的 FAISS 向量库对象。
        """
        if vectorstore is None:
            if embeddings is None:
                raise ValueError("创建新索引时必须提供 embeddings")
            vectorstore = FAISS.from_texts(
                texts=texts, embedding=embeddings, metadatas=metadatas, ids=ids
            )
        else:
            vectorstore.add_texts(texts=texts, metadatas=metadatas, ids=ids)
        return vectorstore

    def delete(self, vectorstore: FAISS, ids: List[str]) -> None:
        """根据文档 ID 删除向量记录。"""
        try:
            vectorstore.delete(ids)
        except Exception:
            # 某些版本可能不支持直接删除，忽略异常以提高兼容性
            pass

    def get_by_id(self, vectorstore: FAISS, doc_id: str):
        """根据文档 ID 获取原始 Document 对象（若存在）。"""
        try:
            return vectorstore.docstore.search(doc_id)
        except Exception:
            return None

    def similarity_search(self, vectorstore: FAISS, query: str, k: int = 5):
        """执行相似度检索，返回最相关的 k 条 Document。"""
        return vectorstore.similarity_search(query, k=k)

    def update_text(
        self,
        vectorstore: FAISS,
        doc_id: str,
        new_text: str,
        new_metadata: Optional[Dict[str, Any]] = None,
        embeddings=None,
    ) -> FAISS:
        """根据 ID 更新文本内容：删除旧记录后以相同 ID 重建。

        参数:
            vectorstore: 向量库对象。
            doc_id: 文档 ID。
            new_text: 新文本内容。
            new_metadata: 新元数据（可选）。
            embeddings: 当需要重建索引且不存在时提供嵌入模型（一般不需要）。

        返回:
            更新后的向量库对象。
        """
        try:
            vectorstore.delete([doc_id])
        except Exception:
            pass
        vectorstore = self.add_texts(
            vectorstore, texts=[new_text], metadatas=[new_metadata] if new_metadata else None, ids=[doc_id], embeddings=embeddings
        )
        return vectorstore
