from __future__ import annotations
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class EvaluationDatasetCreateRequest(BaseModel):
    name: str
    type: str = "tenant"
    status: Optional[str] = None
    data_json: Any


class EvaluationParseAlpacaRequest(BaseModel):
    raw_json: Any
    hint: Optional[str] = None


class EvaluationStartRequest(BaseModel):
    eva_json_id: str
    agent_id: int
    type: Optional[str] = None


class AlpacaItem(BaseModel):
    instruction: str = ""
    input: str = ""
    output: str = ""


class AlpacaParseOutput(BaseModel):
    items: List[AlpacaItem] = Field(default_factory=list)


class EvaluationReviewOutput(BaseModel):
    score: int = Field(default=0, ge=0, le=100)
    opinion: str = ""
