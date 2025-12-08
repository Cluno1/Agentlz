from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field


class AgentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    disabled: Optional[bool] = None
    mcp_agent_ids: Optional[List[int]] = None
    document_ids: Optional[List[str]] = None


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    disabled: Optional[bool] = None
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
