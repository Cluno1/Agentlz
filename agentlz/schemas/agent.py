from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field


class AgentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    disabled: Optional[bool] = None
    system_prompt: Optional[str] = None
    meta: Optional[dict] = None
    mcp_agent_ids: Optional[List[int]] = None
    document_ids: Optional[List[str]] = None


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    disabled: Optional[bool] = None
    system_prompt: Optional[str] = None
    meta: Optional[dict] = None
    mcp_agent_ids: Optional[List[int]] = None
    document_ids: Optional[List[str]] = None


class AgentApiUpdate(BaseModel):
    api_name: Optional[str] = None
    api_key: Optional[str] = None


class AgentChatInput(BaseModel):
    """
    调用 Agent 进行聊天
    
    - `agent_id`: Agent ID 如果没有提供api_name和api_key, 则必须提供agent_id,并且会验证用户token
    - `api_name`: Agent API 名称
    - `api_key`: Agent API 密钥
    - `type`: 聊天类型（0：创建新纪录，1：继续已有纪录,可以获取历史纪录）必须, 默认创建新纪录
    - `record_id`: record的ID（仅在 `type=1` 时有效）如果type是1, 则必须提供record_id, 否则会报错
    - `meta`: 元数据，该信息用于确认该record归宿问题, 必须, 如果type是1, 则通过该meta确认该record是否属于该用户; 如果type是0, 则meta信息用于后续记录的查询与关联历史纪录
    """
    agent_id: Optional[int] = None
    api_name: Optional[str] = None
    api_key: Optional[str] = None
    type: int = Field(default=0, ge=0, le=1)
    record_id: Optional[int] = None
    meta: Optional[dict] = None
    message: str = Field(..., description="用户输入的消息")


class AgentChatHistoryInput(BaseModel):
    """
    查询 Agent 关联的聊天历史记录（Record）分页列表

    - `agent_id`: Agent ID；当未提供 `api_name/api_key` 时必须提供，并验证用户 Token
    - `api_name`: Agent API 名称；与 `api_key` 搭配用于免登录鉴权
    - `api_key`: Agent API 密钥；与 `api_name` 搭配用于免登录鉴权
    - `meta`: 元数据，用于后续记录检索（可选）
    - `page`: 页码（从 1 开始）
    - `per_page`: 每页条数（最大 100）
    - `keyword`: 基于 `name` 的关键字模糊匹配（LIKE）
    """
    agent_id: Optional[int] = None
    api_name: Optional[str] = None
    api_key: Optional[str] = None
    meta: Optional[dict] = None
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=10, ge=1, le=100)
    keyword: Optional[str] = None


class AgentChatSessionInput(BaseModel):
    """
    查询 Agent 关联的聊天会话（Session）分页列表

    - `agent_id`: Agent ID；当未提供 `api_name/api_key` 时必须提供，并验证用户 Token
    - `api_name`: Agent API 名称；与 `api_key` 搭配用于免登录鉴权
    - `api_key`: Agent API 密钥；与 `api_name` 搭配用于免登录鉴权
    - `meta`: 元数据，用于后续记录检索（可选）
    - `record_id`: 记录 ID；必须提供，用于查询该记录关联的会话
    - `page`: 页码（从 1 开始）
    - `per_page`: 每页条数（最大 100）
    """
    agent_id: Optional[int] = None
    api_name: Optional[str] = None
    api_key: Optional[str] = None
    meta: Optional[dict] = None
    record_id: int
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=10, ge=1, le=100)
