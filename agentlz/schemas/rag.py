from typing import List, Dict, Any

from pydantic import BaseModel, Field


class RAGDocument(BaseModel):
    id: str
    content: str = ""
    score: float | None = None
    metadata: Dict[str, Any] | None = None


class RAGRetrieveInput(BaseModel):
    query: str
    top_k: int = 5


class RAGRetrieveOutput(BaseModel):
    items: List[RAGDocument] = Field(default_factory=list)


class RAGRerankInput(BaseModel):
    query: str
    items: List[RAGDocument] = Field(default_factory=list)


class RAGRerankOutput(BaseModel):
    items: List[RAGDocument] = Field(default_factory=list)