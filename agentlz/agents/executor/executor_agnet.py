import os
import sys
import asyncio
from langchain_core.runnables.config import P
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent
from langchain_core.prompts import ChatPromptTemplate
from agentlz.core.model_factory import get_model
from agentlz.core.logger import setup_logging
from agentlz.config.settings import get_settings
from agentlz.schemas.workflow import WorkflowPlan, MCPConfigItem
from agentlz.prompts import EXECUTOR_PROMPT


class MCPChainExecutor:
    def __init__(self, plan: WorkflowPlan):
        self.plan = plan
        self.client = None

    def assemble_mcp(self):
        # 将 WorkflowPlan.mcp_config 列表转换为 MultiServerMCPClient 需要的字典结构
        mcp_dict = {
            item.name: {
                "transport": item.transport,
                "command": item.command,
                "args": item.args,
            }
            for item in self.plan.mcp_config
        }
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
        # 将计划中的链路作为偏好提示传递给代理
        preferred_chain = ", ".join(self.plan.execution_chain) if self.plan.execution_chain else ""
        system_prompt = EXECUTOR_PROMPT + (f"优先按以下顺序使用工具/服务：{preferred_chain}。" if preferred_chain else "")
        llm = get_model(settings)
        if llm is None:
            logger.error("模型未配置：请在 .env 设置 OPENAI_API_KEY 或 CHATOPENAI_API_KEY/CHATOPENAI_BASE_URL")
            return "执行器错误：模型未配置，无法执行链路。"
        # 通过 ChatPromptTemplate 组织提示词与输入；如果 planner 给出 instructions，则一并注入
        template_msgs = [("system", system_prompt)]
        if getattr(self.plan, "instructions", None):
            template_msgs.append(("system", "{instructions}"))
        template_msgs.append(("human", "{input}"))
        # 提示词构建
        prompt = ChatPromptTemplate.from_messages(template_msgs)
        # 创建 LangChain 代理
        try:
            agent = create_agent(model=llm, tools=tools, system_prompt=system_prompt)
        except Exception as e:
            logger.exception("创建 Executor 代理失败：%r", e)
            return "执行器错误：代理创建失败。"
        user_content = input_data if isinstance(input_data, str) else str(input_data)
        try:
            formatted_msgs = prompt.format_messages(input=user_content, instructions=getattr(self.plan, "instructions", ""))
            # 系统提示词由 system_prompt 注入，这里仅传递用户消息
            response = await agent.ainvoke({"messages": [formatted_msgs[-1]]})
        except Exception as e:
            logger.exception("代理执行失败：%r", e)
            return "执行器错误：代理执行失败。"
        try:
            return response["messages"][-1].content if isinstance(response, dict) else response
        except Exception:
            return str(response)




if __name__ == "__main__":
    asyncio.run(main())