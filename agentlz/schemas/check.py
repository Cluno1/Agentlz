from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class CheckInput(BaseModel):
    objectMsg: str = Field(..., description="目标信息，描述了期望达成的任务目标。")
    factMsg: str = Field(..., description="事实信息，描述了上一步工具或Agent实际执行后产生的结果。")
    toolCalls: Optional[List[Dict[str, Any]]] = Field(default=None, description="执行器采集的工具调用日志")

class ToolAssessment(BaseModel):
    mcp_id: str = Field(..., description="MCP 标识（与 planner 阶段可信度表主键一致）")
    server: str = Field(default="", description="工具所属服务器（执行器 toolcall 的 server，即 MCP 代理名）")
    status: str = Field(default="", description="success | error | skipped")
    raw_input: str = Field(default="", description="工具原始输入")
    raw_output: str = Field(default="", description="工具原始输出")
    error_msg: str = Field(default="", description="异常信息（如有）")
    micro_score: int = Field(..., ge=0, le=100, description="该工具的独立评分")
    micro_judge: bool = Field(..., description="该工具是否通过")
    micro_reason: str = Field(default="", description="该工具评分理由")

class CheckOutput(BaseModel):
    judge: bool = Field(..., description="判断结果，True 表示事实符合目标，False 表示不符合。")
    score: int = Field(..., ge=1, le=100, description="对事实信息实现目标程度的评分，范围从1到100。")
    reasoning: str = Field(..., description="给出判断和评分的详细理由。")
    tool_assessments: List[ToolAssessment] = Field(default_factory=list, description="逐工具评估")
