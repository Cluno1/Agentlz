"""统一 SSE 事件构造（agent_service / chain_service 共用，去重）。

零行为变化：本模块的 make_sse 与原 _sse 逐字节等价
（同 EventEnvelope、同 json.dumps(ensure_ascii=False)、同 "event/id/data" 三行帧）。
事件名为现有真实值，仅集中为契约常量，不改 wire。
"""
from __future__ import annotations
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
import json
from typing import Any
from agentlz.schemas.events import EventEnvelope


def sse_now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def to_jsonable(x: Any) -> Any:
    try:
        if hasattr(x, "model_dump"):
            return x.model_dump()
        if hasattr(x, "__dataclass_fields__"):
            return asdict(x)
        if isinstance(x, (dict, list, str, int, float)) or x is None:
            return x
        return str(x)
    except Exception:
        return str(x)


def make_sse(evt: str, payload: Any, *, seq: int, trace_id: str) -> str:
    env = EventEnvelope(evt=evt, seq=seq, ts=sse_now(), trace_id=trace_id, payload=to_jsonable(payload))
    txt = json.dumps(env.model_dump(), ensure_ascii=False)
    return f"event: {evt}\nid: {env.seq}\ndata: {txt}\n\n"


class Evt:
    """事件分类契约（值=现有真实事件名，零行为变化）。"""
    # 文本
    DELTA = "delta"; TEXT = "text"; FINAL = "final"
    # 步骤(PDC)
    PLANNER_PLAN = "planner.plan"; CHECK_SUMMARY = "check.summary"
    # 工具
    CALL_START = "call.start"; CALL_END = "call.end"; EXECUTOR_SUMMARY = "executor.summary"
    # 生命周期
    CHAIN_STEP = "chain.step"
    # 错误
    ERROR = "error"; EXECUTOR_ERROR = "executor.error"
    PLANNER_FAILED = "planner_failed"; EXECUTOR_FAILED = "executor_failed"
