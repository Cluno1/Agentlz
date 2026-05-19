from __future__ import annotations
import json
from agentlz.services.chain.handler import Handler
from agentlz.services.chain.chain_service import ChainContext, get_chain_model
from langchain.agents import create_agent
from langchain_core.prompts import ChatPromptTemplate
from agentlz.core.model_factory import get_model
from agentlz.core.logger import setup_logging
from agentlz.config.settings import get_settings
from agentlz.agents.planner.tools.mcp_config_tool import make_mcp_keyword_tool, _get_mcp_config_by_keyword
from agentlz.schemas.workflow import WorkflowPlan, MCPConfigItem
from agentlz.prompts.planner.planner import PLANNER_SYSTEM_PROMPT


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
            logger = setup_logging(get_settings().log_level)
            ctx.plan = await self._run_planner(ctx)
            # 记录成功步骤，输出为结构化计划对象
            ctx.steps.append({"name": "planner", "status": "passed", "output": ctx.plan})
            # 流式推送：阶段进入（planner）
            self.send_sse(ctx, "chain.step", "planner")
            # 流式推送：规划产出（结构化 WorkflowPlan），供前端渲染
            if getattr(ctx, "plan", None) is not None:
                self.send_sse(ctx, "planner.plan", ctx.plan)
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
        except Exception as e:
            # 记录错误并标记失败步骤
            ctx.errors.append("planner_failed")
            ctx.steps.append({"name": "planner", "status": "failed", "output": {"error": str(e)}})
            ctx.fact_msg = f"规划失败：{e}"
            ctx.stop_chain = True
            try:
                logger.exception("planner_failed: %r", e)
            except Exception:
                pass
            self.send_sse(ctx, "executor.error", {"stage": "planner", "message": str(e)})
        return await super().handle(ctx)

    def next(self, ctx: ChainContext) -> Handler | None:
        """路由到执行节点"""
        if getattr(ctx, "stop_chain", False):
            return None
        # 规划完成后进入执行阶段
        from agentlz.services.chain.steps.step2_executor import ExecutorHandler
        return ExecutorHandler()

    async def _run_planner(self, ctx: ChainContext) -> WorkflowPlan:
        """
        使用 LLM + 工具生成结构化执行计划（WorkflowPlan）。

        过程说明：
        - 构建系统提示与人类输入的对话模板（`PLANNER_PROMPT`）。
        - 注册 `get_mcp_config_by_keyword` 工具，允许 LLM 按关键词查询 MCP 配置。
        - 创建 Agent，期望返回结构化的 `WorkflowPlan` 模型。
        - 返回结构化计划；若模型不可用或未返回结构化响应，生成兜底计划。
        """
        settings = get_settings()
        logger = setup_logging(settings.log_level)
        llm = get_chain_model(ctx, streaming=False)
        if llm is None:
            return WorkflowPlan(execution_chain=[], mcp_config=[], instructions="计划生成失败：模型未配置。")
        # 构建提示词模板：包含系统提示与用户输入占位符
        prompt = ChatPromptTemplate.from_messages([("system", PLANNER_SYSTEM_PROMPT), ("human", "{user_input}")])
        # 注册可调用工具：从关键词解析 MCP 配置
        tools = [make_mcp_keyword_tool(getattr(ctx, "user_id", None), getattr(ctx, "tenant_id", None), getattr(ctx, "agent_id", None))]
        # 创建代理，指定返回结构化 `WorkflowPlan`
        agent = create_agent(model=llm, tools=tools, system_prompt=PLANNER_SYSTEM_PROMPT, response_format=WorkflowPlan)
        # 格式化对话，取最后一条人类消息作为输入
        formatted_msgs = prompt.format_messages(user_input=str(ctx.user_input))
        user_msg = formatted_msgs[-1]
        # 异步调用代理，更契合步骤的异步上下文
        try:
            response = await agent.ainvoke({"messages": [user_msg]})
        except Exception as e:
            fallback = self._fallback_plan_from_mcp(ctx)
            if fallback is not None:
                logger.warning(f"planner model failed, using MCP fallback: {e}")
                return fallback
            raise
        if isinstance(response, dict) and response.get("structured_response") is not None:
            return response["structured_response"]
        fallback = self._fallback_plan_from_mcp(ctx)
        if fallback is not None:
            logger.warning("planner model did not return structured_response, using MCP fallback")
            return fallback
        return WorkflowPlan(execution_chain=[], mcp_config=[], instructions="计划生成失败：未返回结构化计划。")

    def _fallback_plan_from_mcp(self, ctx: ChainContext) -> WorkflowPlan | None:
        raw = _get_mcp_config_by_keyword(
            str(ctx.user_input),
            user_id=getattr(ctx, "user_id", None),
            tenant_id=getattr(ctx, "tenant_id", None),
            agent_id=getattr(ctx, "agent_id", None),
        )
        try:
            rows = json.loads(raw)
        except Exception:
            rows = []
        if not isinstance(rows, list) or not rows:
            return None
        items = []
        for row in rows[:3]:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "")
            transport = str(row.get("transport") or "")
            command = str(row.get("command") or "")
            args = row.get("args") if isinstance(row.get("args"), list) else []
            if name and transport and command:
                items.append(MCPConfigItem(name=name, transport=transport, command=command, args=args))
        if not items:
            return None
        chain = [item.name for item in items]
        instructions = (
            "Planner 结构化输出不可用，已根据 MCP 检索结果生成兜底计划："
            f"按顺序调用 {', '.join(chain)}，将用户原始输入作为工具查询内容，并汇总工具返回结果。"
        )
        return WorkflowPlan(execution_chain=chain, mcp_config=items, instructions=instructions)
