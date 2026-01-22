from __future__ import annotations
from typing import List
from pydantic import BaseModel, Field


class ChunkSemanticInput(BaseModel):
    """
    语义切片输入模型
    
    字段：
    - content：完整 Markdown 文本；
    - chunk_size：单片段最大长度（字符数），用于切片细分控制；
    """
    content: str
    chunk_size: int = Field(default=800, ge=100, le=5000)


class ChunkSemanticOutput(BaseModel):
    """
    语义切片输出模型
    
    字段：
    - segments：切片结果数组，元素为保持原文格式的语义片段；
    """
    segments: List[str] = Field(default_factory=list)

