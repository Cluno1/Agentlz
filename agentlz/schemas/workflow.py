from dataclasses import dataclass
from typing import List
from pydantic import BaseModel, Field


@dataclass
class MCPConfigItem:
    """单个 MCP Agent 的装配配置项。"""
    name: str
    transport: str
    command: str
    args: List[str]


@dataclass
class WorkflowPlan:
    """MCP 工作流编排的结构化输出模型。"""
    execution_chain: List[str]
    mcp_config: List[MCPConfigItem]
    # 额外的执行指示（由 planner 给出，executor 可用于指导工具调用与步骤）
    instructions: str = ""


class ToolCall(BaseModel):
    name: str = ""
    status: str = ""
    input: str = ""
    output: str = ""


class ExecutorTrace(BaseModel):
    calls: List[ToolCall] = Field(default_factory=list)
    final_result: str = ""
