from typing import Any
from pydantic import BaseModel
from agentlz.config.settings import get_settings

class EventEnvelope(BaseModel):
    evt: str
    seq: int
    ts: str
    trace_id: str
    schema_version: str = get_settings().event_schema_version
    payload: Any
