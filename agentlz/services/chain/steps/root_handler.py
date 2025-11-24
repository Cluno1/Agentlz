from __future__ import annotations
from agentlz.services.chain.handler import Handler
from agentlz.services.chain.chain_service import ChainContext


class RootHandler(Handler):
    """根节点路由

    负责记录入口任务与步数配置，并将流程路由到规划节点。
    """

    def __init__(self):
        super().__init__()

    async def handle(self, ctx: ChainContext) -> ChainContext:
        """记录入口信息并继续传递上下文"""
        ctx.steps.append({"name": "root", "status": "passed", "output": {
            "current_task": ctx.current_task,
            "max_step": ctx.max_step,
        }})
        return await super().handle(ctx)

    def next(self, ctx: ChainContext) -> Handler | None:
        """路由到规划节点"""
        from agentlz.services.chain.steps.step1_planner import PlannerHandler
        return PlannerHandler()