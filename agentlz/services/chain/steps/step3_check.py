from __future__ import annotations
from agentlz.services.chain.handler import Handler
from agentlz.services.chain.chain_service import ChainContext, _is_check_passed
from agentlz.services.mcp_service import update_trust_by_tool_assessments
from langchain.agents import create_agent
from langchain_core.prompts import ChatPromptTemplate
from agentlz.core.model_factory import get_model
from agentlz.config.settings import get_settings
from agentlz.prompts.check.check import CHECK_SYSTEM_PROMPT
import json
from agentlz.schemas.check import CheckInput, CheckOutput


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
        if ctx.fact_msg is None:
            return await super().handle(ctx)
        try:
            # 流式推送：阶段进入（check），开始校验展示
            self.send_sse(ctx, "chain.step", "check")
            res = await self._run_check(ctx)
            ctx.check_result = res
            ctx.steps.append({"name": "check", "status": "passed", "output": ctx.check_result})
            # 流式推送：校验摘要（结构化 CheckOutput），用于展示结论与打分
            self.send_sse(ctx, "check.summary", ctx.check_result)
            asses = list(getattr(res, "tool_assessments", []) or [])
            if asses:
                name_to_id = getattr(ctx, "ai_agent_config_map", {}).get("mcp_name_to_id", {})
                update_trust_by_tool_assessments(asses, name_to_id)
        except Exception as e:
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

    async def _run_check(self, ctx: ChainContext):
        """
        校验器：将对象信息、执行摘要与工具调用日志组合，生成结构化校验结果。

        过程说明：
        - 对象信息：用户原始输入 + 规划指示（instructions）。
        - 执行摘要：从 `ctx.fact_msg` 中分离最终结果，并整合 Agent/工具流程段落。
        - 生成提示与创建 Agent，期望返回结构化 `CheckOutput`。
        - 返回结构化校验结果，用于决定链路是否结束或回到规划阶段。
        """
        user_input = str(getattr(ctx, "current_task", ""))
        instructions = str(getattr(getattr(ctx, "plan", None), "instructions", ""))
        object_msg = ("用户输入: " + user_input + "\n" + "规划建议: " + instructions).strip()
        agent_rows: list[str] = []
        for i, s in enumerate(ctx.steps, 1):
            name = s.get("name")
            status = s.get("status")
            agent_rows.append(f"{i:02d}. {name} -> {status}")
        agent_process = "\n".join(agent_rows)
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
        raw_fact = str(ctx.fact_msg)
        marker = "最终结果:\n"
        # 从摘要文本中分离最终结果段，若无标记则使用原始文本
        final_result = raw_fact.split(marker, 1)[1] if marker in raw_fact else raw_fact
        fact_msg = (
            "Agent流程:\n" + agent_process +
            "\n\n执行器MCP流程:\n" + tool_process +
            "\n\n最终执行结果:\n" + final_result
        )
        settings = get_settings()
        llm = get_model(settings)
        # 创建无工具的校验 Agent，指定返回结构化 `CheckOutput`
        agent = create_agent(model=llm, tools=[], system_prompt=CHECK_SYSTEM_PROMPT, response_format=CheckOutput)
        prompt = ChatPromptTemplate.from_messages([
            ("system", CHECK_SYSTEM_PROMPT),
            ("human", "目标 (Object):\n```\n{objectMsg}\n```\n\n事实 (Fact):\n```\n{factMsg}\n```\n\n工具MCP调用日志(JSON):\n```\n{toolCallsJson}\n```"),
        ])
        # 将三段信息以 JSON/文本整合注入到提示中
        msgs = prompt.format_messages(objectMsg=object_msg, factMsg=fact_msg, toolCallsJson=json.dumps(calls))
        resp = await agent.ainvoke({"messages": msgs})
        return resp["structured_response"] if isinstance(resp, dict) and resp.get("structured_response") is not None else CheckOutput.model_validate_json(resp.get("messages", [{}])[-1].get("content", "") if isinstance(resp, dict) else str(resp))
