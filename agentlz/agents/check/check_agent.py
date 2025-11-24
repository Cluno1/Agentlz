from langchain.agents import create_agent
from langchain_core.prompts import ChatPromptTemplate
from agentlz.core.model_factory import get_model
from agentlz.config.settings import get_settings
from agentlz.prompts.check.check import CHECK_SYSTEM_PROMPT
from agentlz.schemas.check import CheckInput, CheckOutput

def _build_agent_and_prompt():
    # 构建用于校验的 Agent（强制结构化输出为 CheckOutput）与提示词模板
    settings = get_settings()
    llm = get_model(settings)
    # 使用与 planner 相同的结构化输出规范：response_format=CheckOutput
    agent = create_agent(model=llm, tools=[], system_prompt=CHECK_SYSTEM_PROMPT, response_format=CheckOutput)
    # 提示词：system 为校验规则，human 注入 objectMsg 与 factMsg 两段文本
    prompt = ChatPromptTemplate.from_messages([
        ("system", CHECK_SYSTEM_PROMPT),
        ("human", "目标 (Object):\n```\n{objectMsg}\n```\n\n事实 (Fact):\n```\n{factMsg}\n```")
    ])
    return agent, prompt

def run_check(input_data: CheckInput) -> CheckOutput:
    # 构建代理与提示词模板（代理使用 response_format=CheckOutput 约束结构化输出）
    agent, prompt = _build_agent_and_prompt()
    # 将输入模型字段注入到 human 模板，得到完整消息序列（含 system 与 human）
    msgs = prompt.format_messages(objectMsg=input_data.objectMsg, factMsg=input_data.factMsg)
    # 调用代理：传入格式化后的消息序列，保持上下文完整
    resp = agent.invoke({"messages": msgs})
    # 若代理返回结构化字段（与 structured_response 一致），直接取用
    if isinstance(resp, dict) and resp.get("structured_response") is not None:
        return resp["structured_response"]
    # 否则回退：提取最后一条消息文本，按 JSON 解析并校验为 CheckOutput
    content = resp.get("messages", [{}])[-1].get("content", "") if isinstance(resp, dict) else str(resp)
    return CheckOutput.model_validate_json(content)

async def arun_check(input_data: CheckInput) -> CheckOutput:
    # 异步版本：逻辑与 run_check 相同，仅调用改为异步
    agent, prompt = _build_agent_and_prompt()
    msgs = prompt.format_messages(objectMsg=input_data.objectMsg, factMsg=input_data.factMsg)
    resp = await agent.ainvoke({"messages": msgs})
    if isinstance(resp, dict) and resp.get("structured_response") is not None:
        return resp["structured_response"]
    content = resp.get("messages", [{}])[-1].get("content", "") if isinstance(resp, dict) else str(resp)
    return CheckOutput.model_validate_json(content)
