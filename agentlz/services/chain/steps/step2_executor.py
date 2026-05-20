from __future__ import annotations
import json
import asyncio
from agentlz.services.chain.handler import Handler
from agentlz.services.chain.chain_service import ChainContext, get_chain_model
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent
from langchain.agents.middleware.types import AgentMiddleware, ToolCallRequest
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import ToolMessage
from agentlz.core.model_factory import get_model
from agentlz.core.logger import setup_logging
from agentlz.config.settings import get_settings
from agentlz.schemas.workflow import ExecutorTrace, ToolCall
from agentlz.prompts.executor.executor import EXECUTOR_SYSTEM_PROMPT
from agentlz.prompts.summary.summary import SUMMARY_SYSTEM_PROMPT
from langchain_core.messages import SystemMessage, HumanMessage


def _looks_like_url(value) -> bool:
    return isinstance(value, str) and (value.startswith("http://") or value.startswith("https://"))


def _json_or_value(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def _extract_url(value) -> str:
    if _looks_like_url(value):
        return str(value)
    value = _json_or_value(value)
    if isinstance(value, (list, tuple)):
        for item in reversed(value):
            url = _extract_url(item)
            if url:
                return url
    if isinstance(value, dict):
        for key in ("url", "endpoint", "server_url"):
            url = value.get(key)
            if _looks_like_url(url):
                return str(url)
        for item in value.values():
            url = _extract_url(item)
            if url:
                return url
    return ""


def _normalize_stdio_args(args):
    args = _json_or_value(args)
    if isinstance(args, tuple):
        return list(args)
    return args if isinstance(args, list) else []


# 执行节点（ExecutorHandler）说明：
# - 根据规划（ctx.plan）调用执行器，运行 MCP 工具链；
# - 将"工具调用摘要 + 最终结果"写入 ctx.fact_msg，并记录步骤；
# - 同步把每次工具调用的结构化日志（name/status/input/output）追加进 ctx.steps，便于审计与校验展示；
# - 下一步路由到校验节点（CheckHandler）。

class ToolTimeoutMiddleware(AgentMiddleware):
    """限制工具调用耗时，并保护副作用工具不被同一轮重复执行。"""

    def __init__(
        self,
        timeout: float = 30.0,
        single_call_tools: set[str] | None = None,
        called_single_tools: set[str] | None = None,
        cached_results: dict[str, str] | None = None,
    ):
        super().__init__()
        self.timeout = timeout
        self.single_call_tools = set(single_call_tools or set())
        # 共享 set：跨外层 PDC 迭代持续，避免链路重启时副作用工具被重复真实调用
        self._called_single_tools: set[str] = called_single_tools if called_single_tools is not None else set()
        # 共享 dict：缓存首次真实结果；后续 LLM 再次请求同一工具时复用，避免合成"否定"消息让 LLM 死循环
        self._cached_results: dict[str, str] = cached_results if cached_results is not None else {}

    async def awrap_tool_call(self, request, handler):
        tool_call = request.tool_call or {}
        tool_name = tool_call.get("name", "unknown")
        tool_call_id = tool_call.get("id", "")

        if tool_name in self.single_call_tools and tool_name in self._called_single_tools:
            # 同一 ctx 内已成功调用过：返回首次真实结果（如有缓存），并引导 LLM 直接出最终答复
            cached = self._cached_results.get(tool_name, "ok")
            from langchain_core.messages import ToolMessage
            return ToolMessage(
                content=(
                    f"工具 {tool_name} 已在本次任务中成功执行，结果为：{cached}。"
                    f"任务已完成，请基于此结果直接给出最终答复，无需再次调用该工具。"
                ),
                tool_call_id=tool_call_id,
            )

        try:
            import asyncio
            result = await asyncio.wait_for(handler(request), timeout=self.timeout)
        except asyncio.TimeoutError:
            from langchain_core.messages import ToolMessage
            return ToolMessage(
                content=f"工具 {tool_name} 调用超时（>{self.timeout}s），已跳过。",
                tool_call_id=tool_call_id,
            )

        if tool_name in self.single_call_tools:
            self._called_single_tools.add(tool_name)
            try:
                content = getattr(result, "content", None)
                if content is not None:
                    self._cached_results[tool_name] = str(content)[:500]
            except Exception:
                pass
        return result


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
            await self._summarize_results(ctx)
            ctx.steps.append({"name": "executor", "status": "passed", "output": ctx.fact_msg})
        except Exception as _exec_err:
            # 关键：捕获 traceback 落日志；否则 PDC 链回退环路时根因永远查不出
            setup_logging(get_settings().log_level).exception(
                f"executor crashed: {type(_exec_err).__name__}: {_exec_err}"
            )
            ctx.errors.append("executor_failed")
            ctx.steps.append({"name": "executor", "status": "failed", "output": {"error": str(_exec_err)}})
            self.send_sse(ctx, "executor.error", {"stage": "handle", "message": str(_exec_err)})
        return await super().handle(ctx)

    def next(self, ctx: ChainContext) -> Handler | None:
        """路由到校验节点"""
        if getattr(ctx, "stop_chain", False):
            return None
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
                mcp_dict[name] = {"transport": "stdio", "command": getattr(item, "command", None), "args": _normalize_stdio_args(getattr(item, "args", []))}
            elif transport in ("http", "sse"):
                # 远端 HTTP/SSE，命令可为 URL 或放在 args 尾部
                url = _extract_url(getattr(item, "command", ""))
                if not url:
                    url = _extract_url(getattr(item, "args", []))
                if not url:
                    continue
                mcp_dict[name] = {"transport": ("streamable_http" if transport == "http" else "sse"), "url": url}
        if not mcp_dict:
            msg = "执行失败：计划不包含可用 MCP 工具配置"
            ctx.tool_calls = []
            ctx.fact_msg = msg
            ctx.stop_chain = True
            self.send_sse(ctx, "executor.error", {"stage": "mcp_config", "message": msg})
            return
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
        if not tools:
            msg = "执行失败：未加载到 MCP 工具"
            ctx.tool_calls = []
            ctx.fact_msg = msg
            ctx.stop_chain = True
            self.send_sse(ctx, "executor.error", {"stage": "tools", "message": msg})
            return
        chain = getattr(plan, "execution_chain", []) or []
        is_only_search = len(chain) == 1 and chain[0] == "search"
        if is_only_search and await self._try_direct_search_execution(ctx, tools):
            return

        settings = get_settings()
        system_prompt = EXECUTOR_SYSTEM_PROMPT
        chain_pref = ", ".join(getattr(plan, "execution_chain", []) or [])
        if chain_pref:
            system_prompt = system_prompt + (
                f"必须严格按以下顺序使用工具/服务：{chain_pref}。"
                "每个工具最多调用一次：拿到工具返回后，立即基于结果给出最终答复，不要再次调用同一工具。"
                "若某工具收到\"任务已完成\"/\"已成功执行\"语义的回复，请直接输出最终答复，不再调用任何工具。"
            )
        llm = get_chain_model(ctx, streaming=False)
        template_msgs = [("system", system_prompt)]
        instr = getattr(plan, "instructions", "")
        if instr:
            template_msgs.append(("system", "{instructions}"))
        template_msgs.append(("human", "{input}"))
        prompt = ChatPromptTemplate.from_messages(template_msgs)
        agent = create_agent(
            model=llm,
            tools=tools,
            system_prompt=system_prompt,
            middleware=[ToolTimeoutMiddleware(
                timeout=30,
                single_call_tools={"send_mail"},
                # ctx 是 dataclass-like 对象，没有 setdefault，直接用 __dict__ 兜底持久化共享状态
                called_single_tools=(
                    getattr(ctx, "_called_single_tools", None)
                    or ctx.__dict__.setdefault("_called_single_tools", set())
                ),
                cached_results=(
                    getattr(ctx, "_tool_cached_results", None)
                    or ctx.__dict__.setdefault("_tool_cached_results", {})
                ),
            )],
            response_format=ExecutorTrace,
        )
        formatted = prompt.format_messages(input=str(ctx.user_input), instructions=instr)
        # 工具回调发射器：在工具开始/结束时触发 `call.start`/`call.end` 事件
        handler = _ToolLogHandler(lambda evt, payload: self.send_sse(ctx, evt, payload))
        resp = await asyncio.wait_for(agent.ainvoke({"messages": formatted}, config={"callbacks": [handler], "recursion_limit": 10}), timeout=180)
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

    async def _summarize_results(self, ctx: ChainContext) -> None:
        """MCP 执行完成后，对工具返回的总结果做一次 LLM 汇总。

        汇总文本写回 ctx.fact_msg，作为最终结果交给 Check 校验并作为 final 呈现；
        无工具输出 / LLM 失败 / 结果为空时保留原始 ctx.fact_msg，不丢数据。
        """
        if getattr(ctx, "stop_chain", False):
            return
        calls = getattr(ctx, "tool_calls", []) or []
        parts = []
        for i, c in enumerate(calls, 1):
            out = str(c.get("output", "") or "").strip()
            if out:
                parts.append(
                    f"[工具{i} {c.get('name','')} @ {c.get('server','')}]\n{out}"
                )
        if not parts:
            return
        material = "\n\n".join(parts)
        task = str(getattr(ctx, "current_task", "") or getattr(ctx, "user_input", ""))
        try:
            llm = get_chain_model(ctx, streaming=False)
            resp = await llm.ainvoke([
                SystemMessage(content=SUMMARY_SYSTEM_PROMPT),
                HumanMessage(
                    content="用户问题：\n" + task
                    + "\n\n工具/MCP 返回的原始结果：\n" + material
                ),
            ])
            content = getattr(resp, "content", resp)
            if isinstance(content, list):
                content = "".join(str(x) for x in content)
            summary = str(content or "").strip()
        except Exception as e:
            setup_logging(get_settings().log_level).warning(
                f"executor.summarize failed: {e}"
            )
            return
        if summary:
            ctx.fact_msg = summary
            try:
                self.send_sse(ctx, "executor.synthesis", summary)
            except Exception:
                pass

    async def _try_direct_search_execution(self, ctx: ChainContext, tools) -> bool:
        search_tool = None
        for tool in tools or []:
            if str(getattr(tool, "name", "")) == "search":
                search_tool = tool
                break
        if search_tool is None:
            return False
        payload = {"query": str(ctx.user_input), "limit": 5, "searchMode": "auto"}
        payload_text = json.dumps(payload, ensure_ascii=False)
        chain = getattr(getattr(ctx, "plan", None), "execution_chain", []) or []
        server_name = str(chain[0]) if chain else "open-websearch"
        self.send_sse(ctx, "call.start", ToolCall(name="search", status="start", input=payload_text, output="", server=server_name))
        try:
            output = await search_tool.ainvoke(payload)
        except Exception as e:
            msg = f"搜索工具调用失败：{e}"
            ctx.tool_calls = [{"name": "search", "status": "error", "input": payload_text, "output": "", "server": server_name}]
            ctx.fact_msg = msg
            ctx.stop_chain = True
            self.send_sse(ctx, "executor.error", {"stage": "tool_call", "message": msg})
            return True
        output_text = str(output)
        call = {"name": "search", "status": "success", "input": payload_text, "output": output_text, "server": server_name}
        ctx.tool_calls = [call]
        ctx.fact_msg = (
            f"工具调用摘要:\n01. search -> success\n服务器: {server_name}\n输入: {payload_text}\n输出: {output_text}"
            f"\n\n最终结果:\n{output_text}"
        )
        self.send_sse(ctx, "call.end", ToolCall(name="search", status="success", input=payload_text, output=output_text, server=server_name))
        self.send_sse(ctx, "executor.summary", ctx.fact_msg)
        return True


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
