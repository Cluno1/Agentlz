from __future__ import annotations
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class DocumentItem(BaseModel):
    id: str
    tenant_id: str
    uploaded_by_user_id: Optional[int] = None
    status: Optional[str] = None
    upload_time: Optional[str] = None
    title: str
    content: Optional[str] = None

class DocumentQuery(BaseModel):
    status: Optional[str] = None
    upload_time_start: Optional[datetime] = None
    upload_time_end: Optional[datetime] = None
    title: Optional[str] = None
    disabled: Optional[bool] = None
    tags: Optional[str] = None
    description: Optional[str] = None
    uploaded_by_user_id: Optional[int] = None

#  文档更新参数
class DocumentUpdate(BaseModel):
    tags: Optional[list[str]] = None
    description: Optional[str] = None
    disabled: Optional[bool] = None

# 文档上传参数
class DocumentUpload(BaseModel):
    document: bytes
    document_type: str # 文档类型,如 md,pdf等
    title: Optional[str] = None
    description: Optional[str] = None
    meta_https: Optional[str] = None
    tags: Optional[list[str]] = None
    type: str = "self" # 上传的文档的租户形式，self表示该文档的tenant_id == ‘default’,tenant表示该文档的tenant_id == user.tenant_id,system表示该文档的tenant_id == ’system‘