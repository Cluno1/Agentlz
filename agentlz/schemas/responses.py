from __future__ import annotations
from typing import List, Optional, Dict, Any
from pydantic import BaseModel



class ScheduleResponse(BaseModel):
    """总调度 Agent（schedule_1_agent）响应结构"""
    """ 目前为测试,需要返回所有内容 """
    query: str
    status: str  # no_plan_agents / missing_tools_or_checks / planned / executed
    # plan agent 相关
    selected_plan_agent_id: Optional[str] = None
    plan_response: Optional[PlanResponse] = None
    # tools agent 相关
    selected_tools_agent_ids: List[str] = []
    steps: Optional[List[PlanStep]] = None

    # check agent 相关
    check_passed: Optional[bool] = None

    # summary and response 
    final_summary: Optional[str] = None

    error: Optional[str] = None


class PlanStep(BaseModel):
    """Plan Agent 输出的单一步骤规范"""
    order: int  # 步骤序号（从 1 开始）
    description: Optional[str] = None  # 步骤说明
    # 工具候选（同类型 tools agent 的 id 集合，需先调用第一个）
    tool_candidates: List[str] = []
    # 本步骤调用工具时建议传入的参数
    params: Dict[str, Any] = {}
    # 本步骤要实现的目标与预期输出
    goal: Optional[str] = None
    expected_output: Optional[str] = None
    # 可选的检查 agent 候选与该步骤的检查期望
    check_candidates: Optional[List[str]] = None
    check_expected: Optional[str] = None

class PlanResponse(BaseModel):
    """Plan Agent 的整体输出（步骤骨架 + 候选集合）"""
    status: str  # planned / failed 等
    agent_id: Optional[str] = None
    # 所有步骤的规范
    steps: List[PlanStep] = []
    # 汇总的工具/检查候选（去重）
    tools_agent_candidates: List[str] = []
    check_agent_candidates: List[str] = []
    # 规划摘要与错误
    summary: Optional[str] = None
    error: Optional[str] = None

class ToolResponse(BaseModel):
    """Tools Agent 的执行结果摘要"""
    status: str  # executed / retry_required / failed / skipped 等
    agent_id: Optional[str] = None  # 实际选用的 tools agent
    tool: Optional[str] = None  # 工具名或函数标识
    params: Dict[str, Any] = {}  # 入参
    output_text: Optional[str] = None  # 文本化输出（如日志、摘要）
    output_data: Optional[Dict[str, Any]] = None  # 结构化输出
    success: bool = False
    elapsed_ms: Optional[int] = None
    error: Optional[str] = None

class CheckResponse(BaseModel):
    """Check Agent 的校验结果"""
    status: str  # passed / failed / error 等
    agent_id: Optional[str] = None
    passed: bool = False
    reason: Optional[str] = None  # 通过/不通过的原因
    expected: Optional[str] = None  # 期望（目标/规则）
    observed: Optional[str] = None  # 实际（观察到的输出）
    score: Optional[float] = None  # 可选评分（0.0-1.0 或 0-100）
    error: Optional[str] = None