from __future__ import annotations
from agentlz.services.chain.handler import Handler
from agentlz.services.chain.chain_service import ChainContext, _is_check_passed


# 校验节点（CheckHandler）说明：
# - 将“对象信息”（用户输入 + 规划建议）与“事实输出”（执行器摘要）组合为检查输入；
# - 过程段落来自 ctx.steps（包含每步 name/status）；结果段落直接使用 ctx.fact_msg；
# - 通过 arun_check 异步调用检查 Agent，返回写入 ctx.check_result 并记录步骤；
# - 根据检查结果决定是否结束链路或回到规划节点重新规划。


class CheckHandler(Handler):
    """校验节点

    对目标对象与事实输出进行结构化校验，写入 `ctx.check_result` 并决定是否结束或回到规划。
    """

    async def handle(self, ctx: ChainContext) -> ChainContext:
        """进行校验，空事实输出时透传，异常时记录错误标记"""
        # 若执行阶段未产出事实输出（ctx.fact_msg 为空），直接透传到下一节点
        if ctx.fact_msg is None:
            return await super().handle(ctx)
        try:
            from agentlz.agents.check.check_agent import arun_check
            from agentlz.schemas.check import CheckInput
            # 组合对象信息：当前任务与规划阶段的 instructions
            user_input = str(getattr(ctx, "current_task", ""))
            instructions = str(getattr(getattr(ctx, "plan", None), "instructions", ""))
            object_msg = ("用户输入: " + user_input + "\n" + "规划建议: " + instructions).strip()
            # Agent流程（高层轨迹）
            agent_rows: list[str] = []
            for i, s in enumerate(ctx.steps, 1):
                name = s.get("name")
                status = s.get("status")
                agent_rows.append(f"{i:02d}. {name} -> {status}")
            agent_process = "\n".join(agent_rows)

            # 执行器MCP流程（工具调用明细）
            tool_rows: list[str] = []
            calls = getattr(ctx, "tool_calls", []) or []
            if calls:
                for i, c in enumerate(calls, 1):
                    name = c.get("name", "")
                    status = c.get("status", "")
                    inp = c.get("input", "")
                    out = c.get("output", "")
                    server = c.get("server", "")
                    tool_rows.append(f"{i:02d}. {name} -> {status}\n服务器: {server}\n输入: {inp}\n输出: {out}")
                tool_process = "\n\n".join(tool_rows)
            else:
                tool_process = "无工具调用"

            # 最终执行结果（从 fact_msg 中提取最终结果段，若不存在标记则直接使用文本）
            raw_fact = str(ctx.fact_msg)
            marker = "最终结果:\n"
            final_result = raw_fact.split(marker, 1)[1] if marker in raw_fact else raw_fact

            # 组装三段结构的 fact_msg
            fact_msg = (
                "Agent流程:\n" + agent_process +
                "\n\n执行器MCP流程:\n" + tool_process +
                "\n\n最终执行结果:\n" + final_result
            )
            # 异步调用检查 Agent，写入检查结果并记录步骤
            res = await arun_check(CheckInput(objectMsg=object_msg, factMsg=fact_msg, toolCalls=calls))
            ctx.check_result = res
            ctx.steps.append({"name": "check", "status": "passed", "output": ctx.check_result})
        except Exception as e:
            # 记录错误并将失败步骤写入轨迹
            ctx.errors.append("check_failed")
            ctx.steps.append({"name": "check", "status": "failed", "output": {"error": str(e)}})
        return await super().handle(ctx)

    def next(self, ctx: ChainContext) -> Handler | None:
        """通过则结束；不通过则清理计划并回到规划节点"""
        # 检查通过则终止链路；否则清理旧计划并回到规划节点
        if _is_check_passed(ctx.check_result):
            return None
        from agentlz.services.chain.steps.step1_planner import PlannerHandler
        ctx.plan = None
        return PlannerHandler()
