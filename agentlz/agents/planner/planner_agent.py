
from langchain.agents import create_agent
from langchain_core.prompts import ChatPromptTemplate
from agentlz.core.model_factory import get_model
from agentlz.core.logger import setup_logging
from agentlz.config.settings import get_settings
from agentlz.agents.planner.tools.mcp_config_tool import get_mcp_config_by_keyword
from agentlz.schemas.workflow import WorkflowPlan
from agentlz.prompts import PLANNER_PROMPT
    
def plan_workflow_chain(user_input: str):
        settings = get_settings()
        logger = setup_logging(settings.log_level)
        llm = get_model(settings)
        if llm is None:
            logger.error("模型未配置：请在 .env 设置 OPENAI_API_KEY 或 CHATOPENAI_API_KEY/CHATOPENAI_BASE_URL")
            return WorkflowPlan(execution_chain=[], mcp_config=[], instructions="计划生成失败：模型未配置。")
        # 提示词构建
        prompt = ChatPromptTemplate.from_messages([
            ("system", PLANNER_PROMPT),
            ("human", "{user_input}"),
        ])
        tools = [get_mcp_config_by_keyword]
        try:
            agent = create_agent(
                model=llm,
                tools=tools,
                system_prompt=PLANNER_PROMPT,
                response_format=WorkflowPlan,
            )
        except Exception as e:
            logger.exception("创建 Planner 代理失败：%r", e)
            return WorkflowPlan(execution_chain=[], mcp_config=[], instructions="计划生成失败：代理创建错误。")

        try:
            formatted_msgs = prompt.format_messages(user_input=user_input)
            user_msg = formatted_msgs[-1]
            response = agent.invoke({
                "messages": [user_msg]
            })
        except Exception as e:
            logger.exception("Planner 代理调用失败：%r", e)
            return WorkflowPlan(execution_chain=[], mcp_config=[], instructions="计划生成失败：代理调用错误。")

        if isinstance(response, dict) and response.get("structured_response") is not None:
            return response["structured_response"]
        logger.error("Planner 未返回结构化计划，原始响应：%r", response)
        return WorkflowPlan(execution_chain=[], mcp_config=[], instructions="计划生成失败：未返回结构化计划。")