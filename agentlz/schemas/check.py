from pydantic import BaseModel, Field

class CheckInput(BaseModel):
    """
    Check Agent 的输入模型
    """
    objectMsg: str = Field(..., description="目标信息，描述了期望达成的任务目标。")
    factMsg: str = Field(..., description="事实信息，描述了上一步工具或Agent实际执行后产生的结果。")

class CheckOutput(BaseModel):
    """
    Check Agent 的输出模型
    """
    judge: bool = Field(..., description="判断结果，True 表示事实符合目标，False 表示不符合。")
    score: int = Field(..., ge=1, le=100, description="对事实信息实现目标程度的评分，范围从1到100。")
    reasoning: str = Field(..., description="给出判断和评分的详细理由。")