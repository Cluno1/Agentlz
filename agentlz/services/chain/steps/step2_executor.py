from __future__ import annotations
from agentlz.services.chain.handler import Handler
from agentlz.services.chain.chain_service import ChainContext
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.callbacks import BaseCallbackHandler
from agentlz.core.model_factory import get_model
from agentlz.core.logger import setup_logging
from agentlz.config.settings import get_settings
from agentlz.schemas.workflow import ExecutorTrace, ToolCall
from agentlz.prompts import EXECUTOR_PROMPT


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
            # 流式推送：阶段进入（executor），前端可切换到执行视图
            self.send_sse(ctx, "chain.step", "executor")
            await self._run_executor(ctx)
            ctx.steps.append({"name": "executor", "status": "passed", "output": ctx.fact_msg})
        except Exception:
            ctx.errors.append("executor_failed")
            ctx.steps.append({"name": "executor", "status": "failed"})
        return await super().handle(ctx)

    def next(self, ctx: ChainContext) -> Handler | None:
        """路由到校验节点"""
        # 执行完成后进入校验阶段
        from agentlz.services.chain.steps.step3_check import CheckHandler
        return CheckHandler()

    async def _run_executor(self, ctx: ChainContext) -> None:
        """
        执行器：按计划调用 MCP 工具链并推送工具级 SSE 事件。

        过程说明：
        - 解析 `ctx.plan.mcp_config`，支持 `stdio/http/sse` 三类传输，构造多服务器客户端。
        - 通过客户端拉取工具列表，创建带工具的 Agent，并注入执行偏好（链路顺序与指示）。
        - 注入 `_ToolLogHandler`，在工具开始/结束时分别推送 `call.start`/`call.end` 事件。
        - 聚合结构化 `calls` 与最终文本，写入 `ctx.tool_calls` 与 `ctx.fact_msg`。
        """
        plan = ctx.plan
        mcp_dict: dict[str, dict] = {}
        for item in getattr(plan, "mcp_config", []) or []:
            transport = str(getattr(item, "transport", "") or "").lower()
            name = getattr(item, "name", "")
            if transport == "stdio":
                # 本地进程直连
                mcp_dict[name] = {"transport": "stdio", "command": getattr(item, "command", None), "args": getattr(item, "args", [])}
            elif transport in ("http", "sse"):
                # 远端 HTTP/SSE，命令可为 URL 或放在 args 尾部
                url = getattr(item, "command", "") if isinstance(getattr(item, "command", ""), str) else ""
                if not (url.startswith("http://") or url.startswith("https://")):
                    args = getattr(item, "args", []) or []
                    url = args[-1] if args else ""
                if not url:
                    continue
                mcp_dict[name] = {"transport": ("streamable_http" if transport == "http" else "sse"), "url": url}
        client = None
        try:
            client = MultiServerMCPClient(mcp_dict)
        except Exception as e:
            client = None
            self.send_sse(ctx, "executor.error", {"stage": "client_init", "message": str(e)})
            setup_logging(get_settings().log_level).error(f"executor.error stage=client_init err={e}")
        tools = []
        if client is not None:
            try:
                tools = await client.get_tools()
            except Exception as e:
                tools = []
                self.send_sse(ctx, "executor.error", {"stage": "get_tools", "message": str(e)})
                setup_logging(get_settings().log_level).error(f"executor.error stage=get_tools err={e}")

        settings = get_settings()
        system_prompt = EXECUTOR_PROMPT
        chain_pref = ", ".join(getattr(plan, "execution_chain", []) or [])
        if chain_pref:
            system_prompt = system_prompt + f"必须严格按以下顺序使用工具/服务：{chain_pref}。禁止直接生成最终结果。"
        llm = get_model(settings)
        template_msgs = [("system", system_prompt)]
        instr = getattr(plan, "instructions", "")
        if instr:
            template_msgs.append(("system", "{instructions}"))
        template_msgs.append(("human", "{input}"))
        prompt = ChatPromptTemplate.from_messages(template_msgs)
        agent = create_agent(model=llm, tools=tools, system_prompt=system_prompt, response_format=ExecutorTrace)
        formatted = prompt.format_messages(input=str(ctx.user_input), instructions=instr)
        # 工具回调发射器：在工具开始/结束时触发 `call.start`/`call.end` 事件
        handler = _ToolLogHandler(lambda evt, payload: self.send_sse(ctx, evt, payload))
        resp = await agent.ainvoke({"messages": formatted}, config={"callbacks": [handler]})
        final_text = resp["messages"][-1].content if isinstance(resp, dict) else str(resp)
        logs = getattr(handler, "calls", [])
        if isinstance(resp, dict) and resp.get("structured_response") is not None:
            sr = resp["structured_response"]
            sr_calls = []
            for c in getattr(sr, "calls", []) or []:
                sr_calls.append({
                    "name": str(getattr(c, "name", "")),
                    "status": str(getattr(c, "status", "")),
                    "input": str(getattr(c, "input", "")),
                    "output": str(getattr(c, "output", "")),
                    "server": str(getattr(c, "server", "")),
                })
            ctx.tool_calls = sr_calls
            ctx.fact_msg = str(getattr(sr, "final_result", ""))
        elif logs:
            chain = getattr(plan, "execution_chain", []) or []
            enriched = []
            for i, c in enumerate(logs, 1):
                server_name = chain[i - 1] if 0 <= (i - 1) < len(chain) else ""
                enriched.append({**c, "server": server_name})
            ctx.tool_calls = enriched
            ctx.fact_msg = ("实际调用链:\n" + ", ".join(chain) + "\n\n" if chain else "") + "工具调用摘要:\n" + "\n\n".join([
                f"{i:02d}. {c.get('name','')} -> {c.get('status','')}\n服务器: {c.get('server','')}\n输入: {c.get('input','')}\n输出: {c.get('output','')}" for i, c in enumerate(enriched, 1)
            ]) + "\n\n最终结果:\n" + str(final_text)
        else:
            ctx.tool_calls = []
            ctx.fact_msg = str(final_text)

        try:
            self.send_sse(ctx, "executor.summary", ctx.fact_msg)
        except Exception:
            pass


class _ToolLogHandler(BaseCallbackHandler):
    def __init__(self, emitter):
        self.calls = []
        self._emit = emitter
        """
        工具调用拦截器：
        - on_tool_start: 记录输入并推送 `call.start`
        - on_tool_end: 填充输出并推送 `call.end`（状态统一映射为 success）
        """

    def on_tool_start(self, serialized, input_str, **kwargs):
        name = ""
        try:
            name = (serialized or {}).get("name") or (serialized or {}).get("kwargs", {}).get("name", "")
        except Exception:
            name = ""
        rec = {"name": str(name), "input": str(input_str), "output": "", "status": "start"}
        self.calls.append(rec)
        try:
            # 推送工具开始事件，包含工具名与输入参数
            payload = ToolCall(name=str(name), status="start", input=str(input_str), output="", server="")
            self._emit("call.start", payload)
        except Exception:
            pass

    def on_tool_end(self, output, **kwargs):
        for c in reversed(self.calls):
            if not c.get("output"):
                c["output"] = str(output)
                c["status"] = "ok"
                break
        try:
            last = self.calls[-1] if self.calls else {"name": "", "input": ""}
            # 推送工具结束事件，统一映射状态为 success，并携带输出
            payload = ToolCall(name=str(last.get("name", "")), status="success", input=str(last.get("input", "")), output=str(output), server="")
            self._emit("call.end", payload)
        except Exception:
            pass
