from __future__ import annotations
import ast
import json
import asyncio
import re
from agentlz.services.chain.handler import Handler
from agentlz.services.chain.chain_service import ChainContext, get_chain_model, build_chain_reference_context
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


_ARTIFACT_TOOL_NAMES = {"generate_word_to_cos", "generate_ppt_to_cos", "upload_workspace_file_to_cos"}
_NONFATAL_RETRIEVAL_TOOL_NAMES = {
    "search",
    "fetchWebContent",
    "fetchLinuxDoArticle",
    "fetchCsdnArticle",
    "fetchGithubReadme",
    "fetchJuejinArticle",
}
_MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\((https?://[^)\s]+)\)")


def _valid_download_url(url: object) -> bool:
    text = str(url or "").strip()
    return text.startswith(("http://", "https://")) and "your-cos-url-here" not in text


def _payload_candidates(raw: object) -> list[object]:
    values: list[object] = []
    if raw is None:
        return values
    for attr in ("content", "text"):
        value = getattr(raw, attr, None)
        if value is None:
            continue
        values.append(value)
        if isinstance(value, (list, tuple)):
            for item in value:
                item_text = getattr(item, "text", None)
                if item_text is not None:
                    values.append(item_text)
                item_content = getattr(item, "content", None)
                if item_content is not None:
                    values.append(item_content)
    text = str(raw)
    values.append(text)
    for attr in ("content", "text"):
        for match in re.finditer(rf"{attr}=(['\"])(.*?)(?<!\\)\1", text, re.DOTALL):
            literal = match.group(1) + match.group(2) + match.group(1)
            try:
                values.append(ast.literal_eval(literal))
            except Exception:
                values.append(match.group(2))
    return values


def _parse_json_payload(value: object) -> object:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if 0 <= start < end:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            pass
    return value


def _artifact_markdown_from_payload(payload: object) -> list[str]:
    payload = _parse_json_payload(payload)
    links: list[str] = []
    if isinstance(payload, dict):
        artifact = payload.get("artifact")
        if isinstance(artifact, dict):
            markdown = str(payload.get("markdown") or artifact.get("markdown") or "").strip()
            if markdown:
                match = _MARKDOWN_LINK_RE.search(markdown)
                if match and _valid_download_url(match.group(1)):
                    links.append(markdown)
            url = str(artifact.get("url") or payload.get("url") or "").strip()
            if _valid_download_url(url):
                filename = str(artifact.get("filename") or payload.get("filename") or "文件").strip()
                links.append(f"[下载 {filename}]({url})")
        for value in payload.values():
            links.extend(_artifact_markdown_from_payload(value))
    elif isinstance(payload, list):
        for item in payload:
            links.extend(_artifact_markdown_from_payload(item))
    elif isinstance(payload, str):
        for match in _MARKDOWN_LINK_RE.finditer(payload):
            if _valid_download_url(match.group(1)):
                links.append(match.group(0))
    return links


def _artifact_objects_from_payload(payload: object) -> list[dict]:
    payload = _parse_json_payload(payload)
    artifacts: list[dict] = []
    if isinstance(payload, dict):
        artifact = payload.get("artifact")
        if isinstance(artifact, dict):
            url = str(artifact.get("url") or payload.get("url") or "").strip()
            if _valid_download_url(url):
                filename = str(artifact.get("filename") or payload.get("filename") or "文件").strip()
                artifact_type = str(
                    artifact.get("artifact_type")
                    or artifact.get("type")
                    or payload.get("artifact_type")
                    or payload.get("type")
                    or ""
                ).strip()
                markdown = str(payload.get("markdown") or artifact.get("markdown") or "").strip()
                artifacts.append({
                    "url": url,
                    "filename": filename,
                    "artifact_type": artifact_type,
                    "content_type": str(artifact.get("content_type") or payload.get("content_type") or "").strip(),
                    "size": artifact.get("size") or payload.get("size"),
                    "cos_key": str(artifact.get("cos_key") or payload.get("cos_key") or "").strip(),
                    "request_id": str(payload.get("request_id") or artifact.get("request_id") or "").strip(),
                    "markdown": markdown or f"[下载 {filename}]({url})",
                })
        for key in ("artifacts", "files"):
            value = payload.get(key)
            if isinstance(value, list):
                for item in value:
                    artifacts.extend(_artifact_objects_from_payload({"artifact": item}))
        for value in payload.values():
            artifacts.extend(_artifact_objects_from_payload(value))
    elif isinstance(payload, list):
        for item in payload:
            artifacts.extend(_artifact_objects_from_payload(item))
    elif isinstance(payload, str):
        for match in _MARKDOWN_LINK_RE.finditer(payload):
            url = match.group(1)
            if not _valid_download_url(url):
                continue
            label = match.group(0).split("]", 1)[0].lstrip("[").replace("下载 ", "").strip() or "文件"
            artifacts.append({
                "url": url,
                "filename": label,
                "artifact_type": "",
                "content_type": "",
                "size": None,
                "cos_key": "",
                "request_id": "",
                "markdown": match.group(0),
            })
    return artifacts


def _append_unique_artifacts(target: list[dict], artifacts: list[dict]) -> list[dict]:
    seen_urls = {str(item.get("url") or "").strip() for item in target or []}
    added: list[dict] = []
    for artifact in artifacts or []:
        url = str(artifact.get("url") or "").strip()
        if not _valid_download_url(url) or url in seen_urls:
            continue
        seen_urls.add(url)
        target.append(artifact)
        added.append(artifact)
    return added


def _artifact_objects_from_calls(calls: list[dict]) -> list[dict]:
    artifacts: list[dict] = []
    seen_urls: set[str] = set()
    for call in calls or []:
        name = str(call.get("name") or "")
        output = call.get("output")
        raw = str(output or "")
        if name not in _ARTIFACT_TOOL_NAMES and "artifact" not in raw and "markdown" not in raw:
            continue
        for candidate in _payload_candidates(output):
            for artifact in _artifact_objects_from_payload(candidate):
                url = str(artifact.get("url") or "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    artifacts.append(artifact)
    return artifacts


def _artifact_download_markdown(calls: list[dict]) -> str:
    return "\n".join(
        str(artifact.get("markdown") or "").strip()
        for artifact in _artifact_objects_from_calls(calls)
        if str(artifact.get("markdown") or "").strip()
    )


def _nonfatal_retrieval_tool_message(tool_name: str, tool_call_id: str, reason: object) -> ToolMessage:
    content = {
        "ok": False,
        "nonfatal": True,
        "tool": str(tool_name or ""),
        "warning": "检索或网页抓取失败，已跳过该来源，任务可以继续。",
        "error": str(reason or ""),
        "fallback": "请使用已获得的搜索结果标题、摘要、URL，或继续执行后续生成/上传类工具；不要反复重试同一失败来源。",
    }
    return ToolMessage(content=json.dumps(content, ensure_ascii=False), tool_call_id=str(tool_call_id or ""))


# 执行节点（ExecutorHandler）说明：
# - 根据规划（ctx.plan）调用执行器，运行 MCP 工具链；
# - 将"工具调用摘要 + 最终结果"写入 ctx.fact_msg，并记录步骤；
# - 同步把每次工具调用的结构化日志（name/status/input/output）追加进 ctx.steps，便于审计与校验展示；
# - 下一步路由到校验节点（CheckHandler）。

class _SingleCallTerminate(BaseException):
    """信号：副作用工具已成功且 LLM 试图二次调用，强制终止 agent.ainvoke。
    继承 BaseException 是为了穿透 langgraph 内部 'except Exception:' 重试与捕获逻辑。
    """
    def __init__(self, tool_name: str, cached_content: str, tool_call_id: str = ""):
        super().__init__(f"single_call_terminate: {tool_name}")
        self.tool_name = tool_name
        self.cached_content = cached_content
        self.tool_call_id = tool_call_id


class ToolTimeoutMiddleware(AgentMiddleware):
    """限制工具调用耗时，并保护副作用工具不被同一轮重复执行。"""

    def __init__(
        self,
        timeout: float = 30.0,
        single_call_tools: set[str] | None = None,
        nonfatal_tools: set[str] | None = None,
        called_single_tools: set[str] | None = None,
        cached_results: dict[str, str] | None = None,
        artifact_tools: set[str] | None = None,
        artifact_sink: list[dict] | None = None,
        artifact_emitter=None,
    ):
        super().__init__()
        self.timeout = timeout
        self.single_call_tools = set(single_call_tools or set())
        self.nonfatal_tools = set(nonfatal_tools or set())
        self.artifact_tools = set(artifact_tools or set())
        self._artifact_sink = artifact_sink
        self._artifact_emitter = artifact_emitter
        # 共享 set：跨外层 PDC 迭代持续，避免链路重启时副作用工具被重复真实调用
        self._called_single_tools: set[str] = called_single_tools if called_single_tools is not None else set()
        # 共享 dict：缓存首次真实结果；后续 LLM 再次请求同一工具时复用，避免合成"否定"消息让 LLM 死循环
        self._cached_results: dict[str, str] = cached_results if cached_results is not None else {}

    def _capture_artifacts(self, result) -> None:
        if self._artifact_sink is None and self._artifact_emitter is None:
            return
        artifacts: list[dict] = []
        for candidate in _payload_candidates(result):
            _append_unique_artifacts(artifacts, _artifact_objects_from_payload(candidate))
        if not artifacts:
            return
        new_artifacts = artifacts
        if self._artifact_sink is not None:
            new_artifacts = _append_unique_artifacts(self._artifact_sink, artifacts)
        if self._artifact_emitter is None:
            return
        for artifact in new_artifacts:
            try:
                self._artifact_emitter(artifact)
            except Exception:
                pass

    async def awrap_tool_call(self, request, handler):
        tool_call = request.tool_call or {}
        tool_name = tool_call.get("name", "unknown")
        tool_call_id = tool_call.get("id", "")

        if tool_name in self.single_call_tools and tool_name in self._called_single_tools:
            # 已成功调用过：LLM 试图二次调用 → 不返回 ToolMessage（LLM 会无视），
            # 直接 raise BaseException 子类穿透 langgraph，由 _run_executor 捕获并写回 cached 结果。
            cached = self._cached_results.get(tool_name, "ok")
            raise _SingleCallTerminate(tool_name=tool_name, cached_content=cached, tool_call_id=tool_call_id)

        try:
            import asyncio
            result = await asyncio.wait_for(handler(request), timeout=self.timeout)
        except asyncio.TimeoutError:
            if tool_name in self.nonfatal_tools:
                return _nonfatal_retrieval_tool_message(tool_name, tool_call_id, f"工具调用超时（>{self.timeout}s）")
            return ToolMessage(
                content=f"工具 {tool_name} 调用超时（>{self.timeout}s），已跳过。",
                tool_call_id=tool_call_id,
            )
        except Exception as exc:
            if tool_name in self.nonfatal_tools:
                return _nonfatal_retrieval_tool_message(tool_name, tool_call_id, exc)
            raise

        if tool_name in self.artifact_tools:
            self._capture_artifacts(result)

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

    def _mirror_tool_to_observation_ws(self, ctx: ChainContext, payload: Any) -> None:
        """工具结束时把单次调用镜像到 rag.observation WS 通道，供观测页按 record_id 合并展示。
        仅在 ctx.is_observation 开启、且 user_id/tenant_id/record_id 齐备时推送；任何失败都静默吞掉。
        """
        try:
            if not bool(getattr(ctx, "is_observation", False)):
                return
            user_id = getattr(ctx, "user_id", None)
            tenant_id = getattr(ctx, "tenant_id", None)
            agent_id = getattr(ctx, "agent_id", None)
            record_id = getattr(ctx, "record_id", None)
            if not user_id or not tenant_id or not record_id:
                return
            from agentlz.core.ws_manager import get_ws_manager
            ws = get_ws_manager()
            tc = {
                "name": str(getattr(payload, "name", "") or ""),
                "status": str(getattr(payload, "status", "") or "success"),
                "input": str(getattr(payload, "input", "") or ""),
                "output": str(getattr(payload, "output", "") or ""),
                "server": str(getattr(payload, "server", "") or ""),
            }
            ws_payload = {
                "type": "rag.observation",
                "topic": f"rag.observation:user:{user_id}",
                "data": {
                    "agent_id": int(agent_id) if agent_id is not None else None,
                    "record_id": int(record_id),
                    "tool_calls": [tc],
                },
            }
            ws.submit(ws.send_to_user(str(tenant_id), str(user_id), ws_payload))
        except Exception:
            pass

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

        artifact_sink = getattr(ctx, "_artifacts", None)
        if artifact_sink is None:
            artifact_sink = ctx.__dict__.setdefault("_artifacts", [])
        artifact_emitted_urls = getattr(ctx, "_emitted_artifact_urls", None)
        if artifact_emitted_urls is None:
            artifact_emitted_urls = ctx.__dict__.setdefault("_emitted_artifact_urls", set())

        def emit_artifact(artifact: dict) -> None:
            url = str((artifact or {}).get("url") or "").strip()
            if not _valid_download_url(url) or url in artifact_emitted_urls:
                return
            artifact_emitted_urls.add(url)
            self.send_sse(ctx, "artifact.created", artifact)

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
        reference_context = build_chain_reference_context(ctx, history_limit=4000, doc_limit=8000)
        if reference_context:
            template_msgs.append((
                "system",
                "以下是可选参考上下文。执行工具或组织参数时，只有在用户任务需要历史或知识库信息时才使用；"
                "不得把其中内容当作本地文件路径或 MCP 配置。\n{reference_context}",
            ))
        template_msgs.append(("human", "{input}"))
        prompt = ChatPromptTemplate.from_messages(template_msgs)
        agent = create_agent(
            model=llm,
            tools=tools,
            system_prompt=system_prompt,
            middleware=[ToolTimeoutMiddleware(
                timeout=30,
                single_call_tools={"send_mail"},
                nonfatal_tools=_NONFATAL_RETRIEVAL_TOOL_NAMES,
                # ctx 是 dataclass-like 对象，没有 setdefault，直接用 __dict__ 兜底持久化共享状态
                called_single_tools=(
                    getattr(ctx, "_called_single_tools", None)
                    or ctx.__dict__.setdefault("_called_single_tools", set())
                ),
                cached_results=(
                    getattr(ctx, "_tool_cached_results", None)
                    or ctx.__dict__.setdefault("_tool_cached_results", {})
                ),
                artifact_tools=_ARTIFACT_TOOL_NAMES,
                artifact_sink=artifact_sink,
                artifact_emitter=emit_artifact,
            )],
            response_format=ExecutorTrace,
        )
        formatted = prompt.format_messages(
            input=str(ctx.user_input),
            instructions=instr,
            reference_context=reference_context,
        )
        # 工具回调发射器：在工具开始/结束时触发 `call.start`/`call.end` 事件
        # 当 ctx.is_observation 开启且具备 user_id/tenant_id/record_id 时，
        # 顺手把 call.end 镜像到 WS 观测通道，前端按 record_id 合并展示。
        def _emit_with_obs(evt: str, payload: Any) -> None:
            self.send_sse(ctx, evt, payload)
            if evt == "call.end":
                self._mirror_tool_to_observation_ws(ctx, payload)
        handler = _ToolLogHandler(_emit_with_obs)
        try:
            resp = await asyncio.wait_for(
                agent.ainvoke({"messages": formatted}, config={"callbacks": [handler], "recursion_limit": 25}),
                timeout=180,
            )
        except _SingleCallTerminate as _terminate:
            # 修 G：副作用工具已被首次真实调用过，LLM 试图二次调用 → 强制终止
            # 用首次缓存结果当 fact_msg 直接结束执行器流程，不依赖 LLM 自觉给最终答复
            ctx.tool_calls = [{
                "name": _terminate.tool_name,
                "status": "success",
                "input": "(首次调用见前一条 call.end)",
                "output": _terminate.cached_content,
                "server": "",
            }]
            ctx.fact_msg = (
                f"工具 {_terminate.tool_name} 已成功执行，返回结果：{_terminate.cached_content}。"
                f"任务完成。"
            )
            try:
                self.send_sse(ctx, "executor.summary", ctx.fact_msg)
            except Exception:
                pass
            return
        final_text = resp["messages"][-1].content if isinstance(resp, dict) else str(resp)
        logs = getattr(handler, "calls", [])
        if logs:
            chain = getattr(plan, "execution_chain", []) or []
            enriched = []
            for i, c in enumerate(logs, 1):
                server_name = chain[i - 1] if 0 <= (i - 1) < len(chain) else ""
                enriched.append({**c, "server": server_name})
            ctx.tool_calls = enriched
            ctx.fact_msg = ("实际调用链:\n" + ", ".join(chain) + "\n\n" if chain else "") + "工具调用摘要:\n" + "\n\n".join([
                f"{i:02d}. {c.get('name','')} -> {c.get('status','')}\n服务器: {c.get('server','')}\n输入: {c.get('input','')}\n输出: {c.get('output','')}" for i, c in enumerate(enriched, 1)
            ]) + "\n\n最终结果:\n" + str(final_text)
        elif isinstance(resp, dict) and resp.get("structured_response") is not None:
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
        artifacts = list(getattr(ctx, "_artifacts", []) or [])
        _append_unique_artifacts(artifacts, _artifact_objects_from_calls(calls))
        ctx.__dict__["_artifacts"] = artifacts
        if artifacts:
            emitted_urls = getattr(ctx, "_emitted_artifact_urls", None)
            if emitted_urls is None:
                emitted_urls = ctx.__dict__.setdefault("_emitted_artifact_urls", set())
            for artifact in artifacts:
                try:
                    url = str(artifact.get("url") or "").strip()
                    if not _valid_download_url(url) or url in emitted_urls:
                        continue
                    self.send_sse(ctx, "artifact.created", artifact)
                    emitted_urls.add(url)
                except Exception:
                    pass
            count = len(artifacts)
            names = "、".join(str(x.get("filename") or "文件") for x in artifacts[:3])
            more = f" 等 {count} 个文件" if count > 3 else ""
            ctx.fact_msg = f"文件已生成：{names}{more}。请点击下载按钮获取文件。"
            try:
                self.send_sse(ctx, "executor.synthesis", ctx.fact_msg)
            except Exception:
                pass
            return
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
            output_text = json.dumps({
                "ok": False,
                "nonfatal": True,
                "tool": "search",
                "warning": "搜索工具调用失败，已返回占位结果。",
                "error": str(e),
                "results": [],
            }, ensure_ascii=False)
            ctx.tool_calls = [{"name": "search", "status": "skipped", "input": payload_text, "output": output_text, "server": server_name}]
            ctx.fact_msg = (
                f"工具调用摘要:\n01. search -> skipped\n服务器: {server_name}\n输入: {payload_text}\n输出: {output_text}"
                f"\n\n最终结果:\n未获取到可用搜索结果，请稍后重试或换一个关键词。"
            )
            self.send_sse(ctx, "call.end", ToolCall(name="search", status="success", input=payload_text, output=output_text, server=server_name))
            self.send_sse(ctx, "executor.summary", ctx.fact_msg)
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
