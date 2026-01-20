from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class ImageAnalyzeInput(BaseModel):
    image_path: str = Field(..., description="本地图片路径，支持 png/jpeg/jpg。")
    prefer_task: Optional[Literal["auto", "text", "table"]] = Field(
        default="auto", description="偏好任务类型：自动、纯文字、表格。"
    )


class ImageAnalyzeOutput(BaseModel):
    main_features: List[str] = Field(default_factory=list, description="图片主体特征短句列表")
    format_type: Literal["table", "text", "mixed"] = Field(
        default="text", description="识别类型：表格/文字/混合"
    )
    extracted_text: str = Field(default="", description="完整文字提取（中文统一输出）")
    table_markdown: str = Field(default="", description="若为表格，提供 Markdown 表格文本")