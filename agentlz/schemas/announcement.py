from __future__ import annotations

from typing import Optional, List
from pydantic import BaseModel, Field


class AnnouncementItem(BaseModel):
    id: int
    tenant_id: str
    title: str
    content: Optional[str] = None
    disabled: Optional[bool] = None
    created_at: Optional[str] = None
    created_by_id: Optional[int] = None
    updated_at: Optional[str] = None
    updated_by_id: Optional[int] = None


class AnnouncementCreate(BaseModel):
    tenant_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    content: Optional[str] = None
    disabled: Optional[bool] = False


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    disabled: Optional[bool] = None


class AnnouncementListResponse(BaseModel):
    rows: List[AnnouncementItem]
    total: int
