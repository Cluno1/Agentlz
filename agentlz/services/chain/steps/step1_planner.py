from __future__ import annotations
import asyncio
import json
import re
from agentlz.services.chain.handler import Handler
from agentlz.services.chain.chain_service import ChainContext, get_chain_model, build_chain_reference_context
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
        # 不传 response_format：避免 LangChain 内部为强制结构化输出而注入 tool_choice="required"
        # —— DeepSeek v4 等模型在 tool_choice="required" 时返回 400（"does not support this
        # tool_choice"），即便 model 字段是 v4-flash，服务端报错仍硬编码 "deepseek-reasoner"。
        # 改为由 prompt 指令引导 LLM 直接输出 JSON，下面 _parse_workflow_plan_from_messages
        # 手动解析；解析失败走 _fallback_plan_from_mcp。
        agent = create_agent(model=llm, tools=tools, system_prompt=PLANNER_SYSTEM_PROMPT)
        # 格式化对话，取最后一条人类消息作为输入
        planner_input = str(ctx.user_input)
        reference_context = build_chain_reference_context(ctx, history_limit=3000, doc_limit=5000)
        if reference_context:
            planner_input = (
                "用户任务：\n"
                + planner_input
                + "\n\n以下是可选参考上下文。只有当用户任务需要历史或知识库信息时才使用；"
                "不要把参考上下文当作 MCP 工具配置，也不要从其中臆造工具。\n"
                + reference_context
            )
        formatted_msgs = prompt.format_messages(user_input=planner_input)
        user_msg = formatted_msgs[-1]
        # 异步调用代理，更契合步骤的异步上下文
        try:
            planner_timeout = float(getattr(settings, "chain_planner_timeout", 120.0) or 120.0)
            response = await asyncio.wait_for(
                agent.ainvoke({"messages": [user_msg]}),
                timeout=planner_timeout,
            )
        except asyncio.TimeoutError:
            fallback = self._fallback_plan_from_mcp(ctx)
            if fallback is not None:
                logger.warning(f"planner model timed out after {planner_timeout}s, using MCP fallback")
                return fallback
            raise TimeoutError(f"Planner 调用超时（>{planner_timeout}s）")
        except Exception as e:
            fallback = self._fallback_plan_from_mcp(ctx)
            if fallback is not None:
                logger.warning(f"planner model failed, using MCP fallback: {e}")
                return fallback
            raise
        # 从 agent 返回中提取最后一条 AI 文本，按 prompt 约定解析为 WorkflowPlan
        plan = self._parse_workflow_plan_from_messages(response, logger)
        if plan is not None:
            return plan
        fallback = self._fallback_plan_from_mcp(ctx)
        if fallback is not None:
            logger.warning("planner LLM 输出无法解析为结构化计划，使用 MCP 兜底")
            return fallback
        return WorkflowPlan(execution_chain=[], mcp_config=[], instructions="计划生成失败：未返回结构化计划。")

    def _parse_workflow_plan_from_messages(self, response: object, logger) -> WorkflowPlan | None:
        """从 create_agent 返回中提取最后一条 AI 文本消息，解析为 WorkflowPlan。

        宽容处理：
        - LLM 可能用 ```json ... ``` 包裹；或在 JSON 前后输出说明性文字。
        - 抠出第一个 `{` 到最后一个 `}` 的子串再 json.loads。
        - 任一环节失败返回 None，由调用方走 fallback。
        """
        messages = []
        if isinstance(response, dict):
            messages = response.get("messages") or []
        elif hasattr(response, "messages"):
            messages = getattr(response, "messages", []) or []
        if not messages:
            return None
        final_text = ""
        for msg in reversed(messages):
            if isinstance(msg, dict):
                content = msg.get("content")
                msg_type = msg.get("type") or msg.get("role") or ""
            else:
                content = getattr(msg, "content", None)
                msg_type = getattr(msg, "type", None) or getattr(msg, "role", None) or ""
            if msg_type in ("ai", "assistant") and isinstance(content, str) and content.strip():
                final_text = content.strip()
                break
        if not final_text:
            return None
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", final_text, re.DOTALL)
        candidate = m.group(1) if m else final_text
        s, e = candidate.find("{"), candidate.rfind("}")
        if s < 0 or e <= s:
            return None
        try:
            data = json.loads(candidate[s:e + 1])
        except Exception as ex:
            logger.warning(f"planner JSON 解析失败: {ex}; preview={final_text[:200]!r}")
            return None
        if not isinstance(data, dict):
            return None
        try:
            items = []
            for it in (data.get("mcp_config") or []):
                if not isinstance(it, dict):
                    continue
                items.append(MCPConfigItem(
                    name=str(it.get("name") or ""),
                    transport=str(it.get("transport") or ""),
                    command=str(it.get("command") or ""),
                    args=[str(x) for x in (it.get("args") or [])],
                ))
            return WorkflowPlan(
                execution_chain=[str(x) for x in (data.get("execution_chain") or [])],
                mcp_config=items,
                instructions=str(data.get("instructions") or ""),
            )
        except Exception as ex:
            logger.warning(f"planner WorkflowPlan 构造失败: {ex}")
            return None

    def _fallback_keywords(self, text: str) -> list[str]:
        candidates = [text]
        lower = text.lower()
        if "@" in text or any(x in text for x in ("邮件", "邮箱", "发送", "发给", "通知")):
            candidates.extend(["邮件发送", "邮件", "发邮件"])
        if any(x in text for x in ("搜索", "联网", "查询", "查找", "网页", "资料")):
            candidates.extend(["联网搜索", "网页搜索", "搜索"])
        if any(x in text for x in ("文件", "文档", "pdf", "PDF", "上传", "解析")):
            candidates.extend(["文件处理", "文档处理", "PDF解析"])
        if any(x in text for x in ("优化", "润色", "改写", "美化", "夸", "措辞")):
            candidates.extend(["文本优化", "文本润色"])
        if (
            "plantuml" in lower
            or "puml" in lower
            or any(x in text for x in ("流程图", "时序图", "架构图", "转PNG", "转 png", "转图片", "生成图片", "画图"))
        ):
            candidates.extend(["PlantUML", "PUML", "puml2png", "流程图", "生成图片"])
        if "http" in lower or "www." in lower:
            candidates.extend(["网页抓取", "网页内容"])

        seen = set()
        result = []
        for item in candidates:
            kw = str(item or "").strip()
            if kw and kw not in seen:
                seen.add(kw)
                result.append(kw)
        return result

    def _tool_names_for_row(self, row: dict, text: str) -> list[str]:
        name = str(row.get("name") or "")
        desc = str(row.get("description") or "")
        haystack = f"{name}\n{desc}"
        tools: list[str] = []
        if "send_mail" in haystack:
            tools.append("send_mail")
        if "render_puml_to_png" in haystack or "puml2png" in haystack:
            tools.append("render_puml_to_png")
        if re.search(r"(?<![A-Za-z0-9_])search(?![A-Za-z0-9_])", haystack):
            tools.append("search")
        if "fetchWebContent" in haystack and any(x in text for x in ("网页", "链接", "正文", "内容")):
            tools.append("fetchWebContent")
        return tools or ([name] if name else [])

    def _fallback_plan_from_mcp(self, ctx: ChainContext) -> WorkflowPlan | None:
        text = str(ctx.user_input)
        rows = []
        seen_keys = set()
        for keyword in self._fallback_keywords(text):
            raw = _get_mcp_config_by_keyword(
                keyword,
                user_id=getattr(ctx, "user_id", None),
                tenant_id=getattr(ctx, "tenant_id", None),
                agent_id=getattr(ctx, "agent_id", None),
            )
            try:
                found = json.loads(raw)
            except Exception:
                found = []
            if not isinstance(found, list):
                continue
            for row in found:
                if not isinstance(row, dict):
                    continue
                key = (
                    str(row.get("name") or ""),
                    str(row.get("transport") or ""),
                    str(row.get("command") or ""),
                )
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                rows.append(row)
        if not rows:
            return None
        items = []
        chain = []
        for row in rows[:3]:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "")
            transport = str(row.get("transport") or "").lower()
            command_raw = str(row.get("command") or "")
            args_raw = row.get("args")

            # DB 里 mcp_agents.command 实际只是 "http"/"sse"/"stdio" 标签；
            # URL/真正命令藏在 args（JSON 字符串）里。Executor 期望 command 直接含 URL（对 http/sse）
            # 或可执行命令（对 stdio）。下面按 transport 解析：
            command = ""
            args_list = []
            if transport in ("http", "sse"):
                # args 形如 '{"mail":{"type":"http","url":"http://..."}}' 或同形 dict
                parsed = args_raw
                if isinstance(parsed, str):
                    try:
                        parsed = json.loads(parsed)
                    except Exception:
                        parsed = None
                url = None
                if isinstance(parsed, dict):
                    # 优先按 name 取嵌套对象的 url；否则任取一个对象的 url
                    inner = parsed.get(name) if name in parsed else next(iter(parsed.values()), None)
                    if isinstance(inner, dict):
                        url = inner.get("url") or inner.get("URL")
                if url:
                    command = str(url)
                    args_list = [str(url)]
            elif transport == "stdio":
                # args 形如 '["mcpstore-cli", "run", "https://..."]' 或同形 list
                parsed = args_raw
                if isinstance(parsed, str):
                    try:
                        parsed = json.loads(parsed)
                    except Exception:
                        parsed = None
                if isinstance(parsed, list):
                    args_list = [str(x) for x in parsed]
                # stdio 的 command 沿用 DB 字段（如 "uvx" / "npx"），若为空且 args 有内容则取首位
                command = command_raw if command_raw and command_raw not in ("stdio",) else (args_list[0] if args_list else "")
            else:
                # 未知 transport：保守沿用 DB 原值
                command = command_raw
                if isinstance(args_raw, list):
                    args_list = [str(x) for x in args_raw]

            if name and transport and command:
                items.append(MCPConfigItem(name=name, transport=transport, command=command, args=args_list))
                for tool_name in self._tool_names_for_row(row, text):
                    if tool_name not in chain:
                        chain.append(tool_name)
        if not items:
            return None
        if not chain:
            chain = [item.name for item in items]
        instructions = (
            "Planner 结构化输出不可用，已根据 MCP 检索结果生成兜底计划："
            f"按顺序调用 {', '.join(chain)}。"
            "从用户输入中提取收件人、标题、正文等参数；如用户要求优化、润色或改写文本，"
            "先完成文本整理后再作为工具输入，并汇总工具返回结果。"
        )
        return WorkflowPlan(execution_chain=chain, mcp_config=items, instructions=instructions)
