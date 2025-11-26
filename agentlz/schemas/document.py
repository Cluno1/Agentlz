from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class DocumentItem(BaseModel):
    id: str
    tenant_id: str
    uploaded_by_user_id: Optional[int] = None
    status: Optional[str] = None
    upload_time: Optional[str] = None
    title: str
    content: Optional[str] = None

#  文档更新参数
class DocumentUpdate(BaseModel):
    uploaded_by_user_id: Optional[int] = None
    status: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None

# 文档上传参数
class DocumentUpload(BaseModel):
    document: bytes
    document_type: str
    title: Optional[str] = None
    description: Optional[str] = None
    meta_https: Optional[str] = None
    tags: Optional[list[str]] = None
    type: str = "self"