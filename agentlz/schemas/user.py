from __future__ import annotations

from typing import Optional, List

from pydantic import BaseModel, Field


class UserItem(BaseModel):
    """用户实体用于列表/详情展示"""

    id: int
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    avatar: Optional[str] = None
    role: Optional[str] = None
    disabled: Optional[bool] = None
    created_at: Optional[str] = None
    created_by_id: Optional[int] = None
    tenant_id: Optional[str] = None


class UserCreate(BaseModel):
    """创建用户请求体（密码字段作为明文传入，写入 password_hash 列）"""

    username: str = Field(..., min_length=1)
    email: Optional[str] = None
    password: Optional[str] = Field(default=None)
    full_name: Optional[str] = None
    avatar: Optional[str] = None
    role: Optional[str] = "user"
    disabled: Optional[bool] = False
    created_by_id: Optional[int] = None


class UserUpdate(BaseModel):
    """更新用户请求体（所有字段可选）"""

    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    full_name: Optional[str] = None
    avatar: Optional[str] = None
    role: Optional[str] = None
    disabled: Optional[bool] = None
    created_by_id: Optional[int] = None


class ListResponse(BaseModel):
    """统一列表响应结构：data + total"""

    data: List[UserItem]
    total: int