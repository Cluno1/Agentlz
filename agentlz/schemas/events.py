from typing import Any
from pydantic import BaseModel

class EventEnvelope(BaseModel):
    evt: str
    seq: int
    ts: str
    trace_id: str
    schema: str = "v1"
    payload: Any

