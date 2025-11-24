from __future__ import annotations
from agentlz.services.chain.handler import Handler
from agentlz.services.chain.chain_service import ChainContext


class PlannerHandler(Handler):
    """规划节点

    基于用户输入生成结构化执行计划（例如 WorkflowPlan），写入 `ctx.plan` 并记录步骤。
    """

    async def handle(self, ctx: ChainContext) -> ChainContext:
        """生成并写入计划，失败时记录错误标记"""
        try:
            from agentlz.agents.planner.planner_agent import plan_workflow_chain
            ctx.plan = plan_workflow_chain(str(ctx.user_input))
            ctx.steps.append({"name": "planner", "status": "passed", "output": ctx.plan})
        except Exception:
            ctx.errors.append("planner_failed")
            ctx.steps.append({"name": "planner", "status": "failed"})
        return await super().handle(ctx)

    def next(self, ctx: ChainContext) -> Handler | None:
        """路由到执行节点"""
        from agentlz.services.chain.steps.step2_executor import ExecutorHandler
        return ExecutorHandler()