import os
import sys
import asyncio
from langchain_core.runnables.config import P
from langchain_core.callbacks import BaseCallbackHandler
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent
from langchain_core.prompts import ChatPromptTemplate
from agentlz.core.model_factory import get_model
from agentlz.core.logger import setup_logging
from agentlz.config.settings import get_settings
from agentlz.schemas.workflow import WorkflowPlan, ExecutorTrace
from agentlz.prompts.executor.executor import EXECUTOR_SYSTEM_PROMPT


# 执行器说明：
# - 组装 MCP 客户端（支持 stdio/http/sse）
# - 创建带工具的代理并执行用户任务
# - 通过回调拦截每次工具调用的真实输入/输出
# - 返回“工具调用摘要 + 最终结果”文本，同时以结构化数据保存在 last_calls/last_final

class MCPChainExecutor:
    def __init__(self, plan: WorkflowPlan):
        self.plan = plan
        self.client = None
        # 最近一次执行的工具调用日志（按顺序记录）
        self.last_calls = []
        # 最近一次执行的最终文本结果（代理返回的最后消息）
        self.last_final = ""

    def assemble_mcp(self):
        # 将 WorkflowPlan.mcp_config 列表转换为 MultiServerMCPClient 需要的字典结构
        # 支持 stdio/http/sse 三类传输，并对 URL 做兜底解析
        mcp_dict = {}
        for item in self.plan.mcp_config:
            transport = str(item.transport or "").lower()
            if transport == "stdio":
                mcp_dict[item.name] = {
                    "transport": "stdio",
                    "command": item.command,
                    "args": item.args,
                }
            elif transport == "http":
                url = item.command if isinstance(item.command, str) else ""
                if not (url.startswith("http://") or url.startswith("https://")):
                    url = item.args[-1] if item.args else ""
                if not url:
                    continue
                mcp_dict[item.name] = {
                    "transport": "streamable_http",
                    "url": url,
                }
            elif transport == "sse":
                url = item.command if isinstance(item.command, str) else ""
                if not (url.startswith("http://") or url.startswith("https://")):
                    url = item.args[-1] if item.args else ""
                if not url:
                    continue
                mcp_dict[item.name] = {
                    "transport": "sse",
                    "url": url,
                }
            else:
                continue
        try:
            self.client = MultiServerMCPClient(mcp_dict)
        except Exception as e:
            settings = get_settings()
            logger = setup_logging(settings.log_level)
            logger.exception("创建 MCP 客户端失败：%r", e)
            self.client = None

    async def execute_chain(self, input_data):
        """
        使用 MCP 工具集合创建 LangChain 代理并执行用户任务。
        回调拦截器会采集每次工具调用的输入/输出，并以结构化形式暴露到 last_calls。
        """
        self.assemble_mcp()
        settings = get_settings()
        logger = setup_logging(settings.log_level)
        tools = []
        if self.client is not None:
            try:
                tools = await self.client.get_tools()
            except Exception as e:
                logger.exception("加载 MCP 工具失败：%r", e)
                tools = []
        else:
            logger.warning("MCP 客户端不可用，将在无工具模式下执行。")
        # 将计划中的链路作为偏好提示传递给代理（强约束工具顺序）
        preferred_chain = ", ".join(self.plan.execution_chain) if self.plan.execution_chain else ""
        system_prompt = EXECUTOR_SYSTEM_PROMPT + (f"必须严格按以下顺序使用工具/服务：{preferred_chain}。禁止直接生成最终结果。" if preferred_chain else "")
        llm = get_model(settings)
        # 通过 ChatPromptTemplate 组织提示词与输入；如果 planner 给出 instructions，则一并注入
        template_msgs = [("system", system_prompt)]
        if getattr(self.plan, "instructions", None):
            template_msgs.append(("system", "{instructions}"))
        template_msgs.append(("human", "{input}"))
        # 提示词构建
        prompt = ChatPromptTemplate.from_messages(template_msgs)
        # 创建 LangChain 代理
        agent = create_agent(model=llm, tools=tools, system_prompt=system_prompt, response_format=ExecutorTrace)
        user_content = input_data if isinstance(input_data, str) else str(input_data)
        try:
            formatted_msgs = prompt.format_messages(input=user_content, instructions=getattr(self.plan, "instructions", ""))
            # 注入回调以拦截每次工具调用的输入/输出
            handler = _ToolLogHandler()
            response = await agent.ainvoke({"messages": formatted_msgs}, config={"callbacks": [handler]})
        except Exception as e:
            logger.exception("代理执行失败：%r", e)
            return "执行器错误：代理执行失败。"
        final_text = response["messages"][-1].content if isinstance(response, dict) else str(response)
        logs = getattr(handler, "calls", [])

        # 分支1：如果模型返回了结构化响应（ExecutorTrace），解析其中的 calls/final_result
        # - 同样转换为结构化 last_calls，并生成可读摘要文本
        if isinstance(response, dict) and response.get("structured_response") is not None:
            sr = response["structured_response"]
            rows = []
            sr_calls = []
            for i, c in enumerate(getattr(sr, "calls", []) or [], 1):
                name = getattr(c, "name", "")
                status = getattr(c, "status", "")
                inp = getattr(c, "input", "")
                out = getattr(c, "output", "")
                server_name = getattr(c, "server", "")
                sr_calls.append({"name": str(name), "status": str(status), "input": str(inp), "output": str(out), "server": str(server_name)})
                rows.append(f"{i:02d}. {name} -> {status}\n服务器: {server_name}\n输入: {inp}\n输出: {out}")
            process = "\n\n".join(rows)
            final_result = getattr(sr, "final_result", "")
            self.last_calls = sr_calls
            self.last_final = str(final_result)
            return final_result
            
        # 分支2：优先使用回调拦截到的真实工具调用日志（logs）
        # - 将结构化日志保存到 last_calls/last_final
        # - 构造可读摘要（含每次调用的输入/输出）并返回，便于在校验阶段展示
        if logs:
            rows = []
            enriched = []
            chain = self.plan.execution_chain or []
            for i, c in enumerate(logs, 1):
                server_name = chain[i - 1] if 0 <= (i - 1) < len(chain) else ""
                cc = {**c, "server": server_name}
                enriched.append(cc)
                rows.append(
                    f"{i:02d}. {c.get('name','')} -> {c.get('status','')}\n服务器: {server_name}\n输入: {c.get('input','')}\n输出: {c.get('output','')}"
                )
            self.last_calls = enriched
            self.last_final = str(final_text)
            process = "\n\n".join(rows)
            chain_text = ", ".join(chain) if chain else ""
            prefix = ("实际调用链:\n" + chain_text + "\n\n") if chain_text else ""
            return (prefix + "工具调用摘要:\n" + process + "\n\n最终结果:\n" + str(final_text)).strip()
            
      

        self.last_calls = []
        self.last_final = str(final_text)
        return final_text


class _ToolLogHandler(BaseCallbackHandler):
    def __init__(self):
        self.calls = []

    def on_tool_start(self, serialized, input_str, **kwargs):
        # 尝试解析工具名（兼容不同序列化结构），并记录输入
        name = ""
        try:
            name = (serialized or {}).get("name") or (serialized or {}).get("kwargs", {}).get("name", "")
        except Exception:
            name = ""
        self.calls.append({"name": str(name), "input": str(input_str), "output": "", "status": "start"})

    def on_tool_end(self, output, **kwargs):
        # 将最近一次未补充输出的记录填充结果并标记为 ok
        for c in reversed(self.calls):
            if not c.get("output"):
                c["output"] = str(output)
                c["status"] = "ok"
                break




if __name__ == "__main__":
    asyncio.run(main())
