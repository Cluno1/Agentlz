from __future__ import annotations
from agentlz.services.chain.handler import Handler
from agentlz.services.chain.chain_service import ChainContext


# 执行节点（ExecutorHandler）说明：
# - 根据规划（ctx.plan）调用执行器，运行 MCP 工具链；
# - 将“工具调用摘要 + 最终结果”写入 ctx.fact_msg，并记录步骤；
# - 同步把每次工具调用的结构化日志（name/status/input/output）追加进 ctx.steps，便于审计与校验展示；
# - 下一步路由到校验节点（CheckHandler）。

class ExecutorHandler(Handler):
    """执行节点

    根据规划调用工具/服务执行步骤，写入事实输出 `ctx.fact_msg` 并记录步骤。
    """

    async def handle(self, ctx: ChainContext) -> ChainContext:
        """按计划执行，空计划时透传，异常时记录错误标记"""
        if not getattr(ctx, "plan", None):
            return await super().handle(ctx)
        try:
            from agentlz.agents.executor.executor_agnet import MCPChainExecutor
            exe = MCPChainExecutor(ctx.plan)
            ctx.fact_msg = await exe.execute_chain(ctx.user_input)
            ctx.steps.append({"name": "executor", "status": "passed", "output": ctx.fact_msg})
            ctx.tool_calls = getattr(exe, "last_calls", []) or []
        except Exception:
            ctx.errors.append("executor_failed")
            ctx.steps.append({"name": "executor", "status": "failed"})
        return await super().handle(ctx)

    def next(self, ctx: ChainContext) -> Handler | None:
        """路由到校验节点"""
        # 执行完成后进入校验阶段
        from agentlz.services.chain.steps.step3_check import CheckHandler
        return CheckHandler()
