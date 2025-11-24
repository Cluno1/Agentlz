from __future__ import annotations
from typing import Any, Optional, Dict, List
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
