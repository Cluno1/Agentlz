from __future__ import annotations
from typing import Any, Optional, Dict, List
import json
from datetime import datetime
from uuid import uuid4
from dataclasses import asdict
from agentlz.schemas.events import EventEnvelope
from agentlz.schemas.workflow import ToolCall
from .handler import Handler


class ChainContext:
    """责任链运行上下文

    承载一次链路执行过程中跨节点需要共享与记录的全部数据。

    用途：
    - 在 Planner→Executor→Check 节点间传递规划、执行输出与校验结果
    - 记录每步状态与输出，便于审计与排错
    - 保存运行元数据（当前任务、步数上限、会话/租户、配置与历史）
    """

    def __init__(self, user_input: Any):
        self.user_input = user_input
        self.plan: Optional[Any] = None
        self.fact_msg: Optional[Any] = None
        self.check_result: Optional[Any] = None
        self.errors: List[str] = []
        self.steps: List[Dict[str, Any]] = []
        self.tool_calls: List[Dict[str, Any]] = []
        self.ai_agent_config_map: Dict[str, Any] = {}
        self.execution_history: str = ""
        self.current_task: str = ""
        self.max_step: int = 6
        self.session_id: Optional[str] = None
        self.tenant_id: Optional[str] = None





def _is_check_passed(res: Any) -> bool:
    """统一判断校验结果是否通过

    兼容常见返回结构：
    - 仅依据 judge/score 字段：
      - judge 为 True 视为通过
      - 或 score 数值 ≥ 80 视为通过
    """
    try:
        if res is None:
            return False
        # 情况1：返回为字典结构（如从 JSON 解析的结果）——仅读取 judge/score
        if isinstance(res, dict):
            j = res.get("judge")
            if isinstance(j, bool):
                return j
            sc = res.get("score")
            if isinstance(sc, (int, float)):
                return sc >= 80
            return False
        # 情况2：返回为对象结构（如 CheckOutput 实例）——仅读取 judge/score
        if hasattr(res, "judge") and isinstance(getattr(res, "judge"), bool):
            return getattr(res, "judge")
        if hasattr(res, "score") and isinstance(getattr(res, "score"), (int, float)):
            return getattr(res, "score") >= 80
    except Exception:
        return False
    return False


    


async def run_chain(user_input: Any, *, max_steps: int = 6) -> ChainContext:
    """入口执行器

    初始化 `ChainContext`，设定任务与步数上限，启动根节点并按节点自决策进行跳转。
    当校验通过或达到步数上限时结束。
    """
    from .steps.root_handler import RootHandler

    ctx = ChainContext(user_input)
    ctx.current_task = str(user_input)
    ctx.max_step = max_steps
    root = RootHandler()
    steps = 0
    cur: Optional[Handler] = root
    while cur is not None and steps < max_steps:
        steps += 1
        ctx = await cur.handle(ctx)
        nxt = cur.next(ctx)
        if nxt is None:
            break
        cur = nxt
    return ctx


async def stream_chain_generator(*, user_input: str, tenant_id: str, claims: Dict[str, Any]):
    """
    SSE 事件流生成器（异步生成器）。

    功能：按责任链 `Root → Planner → Executor → Check` 的推进顺序，
    逐步输出带类型的 SSE 事件帧。

    输入：
    - user_input: 用户输入文本
    - tenant_id: 多租户标识
    - claims: 鉴权声明（JWT解析结果）

    输出：
    - 文本帧字符串，每帧包含 `event:`/`id:`/`data:` 字段，`data` 为 `EventEnvelope` 的 JSON

    事件类型：
    - chain.step: 当前阶段名（root/planner/executor/check）
    - planner.plan: 结构化计划（WorkflowPlan）
    - call.end: 工具调用结束（ToolCall），status 映射 ok→success
    - check.summary: 校验汇总（CheckOutput）
    - final: 最终结果文本

    说明：在异步生成器中直接 `yield` 单帧字符串；不使用 `yield from`。
    若未来事件体较大需要分块，可将 `_sse` 改为子生成器并在此处迭代。
    """
    trace_id = str(uuid4())
    seq = 1

    def _now():
        """返回 UTC ISO8601 时间戳（附加 Z）用于事件壳 `ts` 字段。"""
        return datetime.utcnow().isoformat() + "Z"

    def _sse(evt: str, payload: Any) -> str:
        """构造单帧 SSE 文本。

        - 输入：事件类型 `evt` 与负载 `payload`
        - 处理：将负载序列化为可 JSON 的对象，封装为 `EventEnvelope`
        - 输出：符合 SSE 规范的单帧字符串（`event/id/data`）
        """
        #把 payload 变成可JSON对象（把“非基础类型”安全地转换成可序列化结构）
        nonlocal seq
        try:
            if hasattr(payload, "model_dump"):
                data_obj = payload.model_dump()
            elif hasattr(payload, "__dataclass_fields__"):
                data_obj = asdict(payload)
            elif isinstance(payload, (dict, list, str, int, float)) or payload is None:
                data_obj = payload
            else:
                data_obj = str(payload)
        except Exception:
            data_obj = str(payload)
        env = EventEnvelope(evt=evt, seq=seq, ts=_now(), trace_id=trace_id, payload=data_obj)
        seq += 1
        txt = json.dumps(env.model_dump(), ensure_ascii=False)
        return f"event: {evt}\nid: {env.seq}\ndata: {txt}\n\n"

    from .steps.root_handler import RootHandler
    from .steps.step1_planner import PlannerHandler
    from .steps.step2_executor import ExecutorHandler
    from .steps.step3_check import CheckHandler

    import asyncio
    q: asyncio.Queue[str] = asyncio.Queue()

    def emit(evt: str, payload: Any) -> None:
        # 步骤层调用的统一发射器：
        # - 将事件转为 SSE 帧文本后写入队列，供 HTTP 层逐帧发送
        try:
            q.put_nowait(_sse(evt, payload))
        except Exception:
            pass

    ctx = ChainContext(user_input)
    ctx.current_task = str(user_input)
    ctx.sse_emitter = emit

    async def _run() -> None:
        cur = RootHandler()
        while cur is not None:
            ctx_local = await cur.handle(ctx)
            nxt = cur.next(ctx_local)
            if nxt is None:
                break
            cur = nxt
        # 链路完成后统一推送最终文本事件，并写入队列结束标记
        final_text = str(getattr(ctx, "fact_msg", ""))
        emit("final", final_text)
        q.put_nowait("__END__")

    task = asyncio.create_task(_run())
    while True:
        frame = await q.get()
        if frame == "__END__":
            break
        yield frame
