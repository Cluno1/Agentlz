
from langchain.agents import create_agent
from langchain_core.prompts import ChatPromptTemplate
from agentlz.core.model_factory import get_model
from agentlz.config.settings import get_settings
from agentlz.agents.planner.tools.mcp_config_tool import get_mcp_config_by_keyword
from agentlz.schemas.workflow import WorkflowPlan
from agentlz.prompts import PLANNER_PROMPT
    
def plan_workflow_chain(user_input: str):
        settings = get_settings()
        llm = get_model(settings)
        if llm is None:
            raise ValueError("Model is not configured. Please set OPENAI_API_KEY or CHATOPENAI_API_KEY/CHATOPENAI_BASE_URL in .env")
        # 使用 ChatPromptTemplate 组织提示词
        prompt = ChatPromptTemplate.from_messages([
            ("system", PLANNER_PROMPT),
            ("human", "{user_input}"),
        ])
        tools = [get_mcp_config_by_keyword]
        agent = create_agent(
            model=llm,
            tools=tools,
            system_prompt=PLANNER_PROMPT,
            response_format=WorkflowPlan,
        )
        # 通过模板生成消息，只传递用户消息给 Agent（系统提示词由 system_prompt 提供）
        formatted_msgs = prompt.format_messages(user_input=user_input)
        user_msg = formatted_msgs[-1]
        response = agent.invoke({
            "messages": [user_msg]
        })
        # 返回结构化响应（dataclass）；严格模式：无结构化响应直接抛错，便于定位问题
        if isinstance(response, dict) and response.get("structured_response") is not None:
            return response["structured_response"]
        raise ValueError(f"WorkflowPlan structured_response missing. Raw response: {response!r}")