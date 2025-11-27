"""
向量维度扩展工具
用于将低维向量通过补零扩展到目标维度
"""
import numpy as np
from typing import List, Union
from langchain_core.embeddings import Embeddings


class DimensionExtendedEmbeddings(Embeddings):
    """包装器，用于将嵌入模型的输出扩展到目标维度"""
    
    def __init__(self, base_embeddings: Embeddings, target_dimension: int):
        """
        初始化维度扩展包装器
        
        Args:
            base_embeddings: 基础嵌入模型
            target_dimension: 目标维度（如1536）
        """
        self.base_embeddings = base_embeddings
        self.target_dimension = target_dimension
    
    def _extend_vector(self, vector: List[float]) -> List[float]:
        """将向量通过补零扩展到目标维度"""
        current_dim = len(vector)
        if current_dim >= self.target_dimension:
            # 如果当前维度已经大于等于目标维度，截断或直接使用
            return vector[:self.target_dimension]
        else:
            # 补零扩展到目标维度
            extended_vector = vector + [0.0] * (self.target_dimension - current_dim)
            return extended_vector
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """嵌入文档列表"""
        # 获取基础嵌入
        base_embeddings = self.base_embeddings.embed_documents(texts)
        # 扩展每个向量
        extended_embeddings = [self._extend_vector(vec) for vec in base_embeddings]
        return extended_embeddings
    
    def embed_query(self, text: str) -> List[float]:
        """嵌入单个查询"""
        # 获取基础嵌入
        base_embedding = self.base_embeddings.embed_query(text)
        # 扩展向量
        extended_embedding = self._extend_vector(base_embedding)
        return extended_embedding
    
    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """异步嵌入文档列表"""
        base_embeddings = await self.base_embeddings.aembed_documents(texts)
        extended_embeddings = [self._extend_vector(vec) for vec in base_embeddings]
        return extended_embeddings
    
    async def aembed_query(self, text: str) -> List[float]:
        """异步嵌入单个查询"""
        base_embedding = await self.base_embeddings.aembed_query(text)
        extended_embedding = self._extend_vector(base_embedding)
        return extended_embedding