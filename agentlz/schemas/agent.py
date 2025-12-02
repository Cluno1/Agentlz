from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel


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