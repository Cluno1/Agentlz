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


class DocumentUpdate(BaseModel):
    uploaded_by_user_id: Optional[int] = None
    status: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None