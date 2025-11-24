from __future__ import annotations
from agentlz.services.chain.handler import Handler
from agentlz.services.chain.chain_service import ChainContext, _is_check_passed


class CheckHandler(Handler):
    """校验节点

    对目标对象与事实输出进行结构化校验，写入 `ctx.check_result` 并决定是否结束或回到规划。
    """

    async def handle(self, ctx: ChainContext) -> ChainContext:
        """进行校验，空事实输出时透传，异常时记录错误标记"""
        if ctx.fact_msg is None:
            return await super().handle(ctx)
        try:
            from agentlz.agents.check.check_agent_1 import get_check_agent
            checker = get_check_agent()
            obj = str(getattr(ctx, "plan", ""))
            res = await checker.ainvoke({"objectMsg": obj, "factMsg": str(ctx.fact_msg)})
            ctx.check_result = res
            ctx.steps.append({"name": "check", "status": "passed", "output": ctx.check_result})
        except Exception as e:
            ctx.errors.append("check_failed")
            ctx.steps.append({"name": "check", "status": "failed", "output": {"error": str(e)}})
        return await super().handle(ctx)

    def next(self, ctx: ChainContext) -> Handler | None:
        """通过则结束；不通过则清理计划并回到规划节点"""
        if _is_check_passed(ctx.check_result):
            return None
        from agentlz.services.chain.steps.step1_planner import PlannerHandler
        ctx.plan = None
        return PlannerHandler()