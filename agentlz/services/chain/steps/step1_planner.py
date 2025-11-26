from __future__ import annotations
from agentlz.services.chain.handler import Handler
from agentlz.services.chain.chain_service import ChainContext


# 规划节点（PlannerHandler）说明：
# - 接收用户输入，调用 planner 生成结构化计划（如 WorkflowPlan）；
# - 将计划写入 ctx.plan，并记录步骤轨迹（passed/failed）；
# - 下一步固定路由到执行节点（ExecutorHandler）。

class PlannerHandler(Handler):
    """规划节点

    基于用户输入生成结构化执行计划（例如 WorkflowPlan），写入 `ctx.plan` 并记录步骤。
    """

    async def handle(self, ctx: ChainContext) -> ChainContext:
        """生成并写入计划，失败时记录错误标记"""
        try:
            # 调用 planner 生成结构化工作流计划
            from agentlz.agents.planner.planner_agent import plan_workflow_chain
            ctx.plan = plan_workflow_chain(str(ctx.user_input))
            # 记录成功步骤，输出为结构化计划对象
            ctx.steps.append({"name": "planner", "status": "passed", "output": ctx.plan})
            # 基于 (name, transport, command) 构建一次链路内的 name→id 映射缓存
            try:
                from agentlz.repositories.mcp_repository import get_mcp_agents_by_unique
                items = getattr(ctx.plan, "mcp_config", []) or []
                triplets = [
                    (getattr(it, "name", ""), getattr(it, "transport", ""), getattr(it, "command", ""))
                    for it in items
                ]
                rows = get_mcp_agents_by_unique([t for t in triplets if all(t)]) if triplets else []
                # 由于同名不同传输/命令也允许存在，这里以“计划内唯一出现”为前提，将 name 映射到对应 id
                name_to_id = {str(r["name"]): int(r["id"]) for r in rows if "id" in r and "name" in r}
                ctx.ai_agent_config_map["mcp_name_to_id"] = name_to_id
                ctx.ai_agent_config_map["mcp_selected_rows"] = rows
            except Exception:
                pass
        except Exception:
            # 记录错误并标记失败步骤
            ctx.errors.append("planner_failed")
            ctx.steps.append({"name": "planner", "status": "failed"})
        return await super().handle(ctx)

    def next(self, ctx: ChainContext) -> Handler | None:
        """路由到执行节点"""
        # 规划完成后进入执行阶段
        from agentlz.services.chain.steps.step2_executor import ExecutorHandler
        return ExecutorHandler()
