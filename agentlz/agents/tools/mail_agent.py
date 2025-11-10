from typing import Any

from langchain.agents import create_agent

from agentlz.config.settings import get_settings
from agentlz.core.model_factory import get_model
from agentlz.tools.email import send_email
from agentlz.prompts.tools.mail_prompt import MAIL_SYSTEM_PROMPT, MAIL_USER_PROMPT_TEMPLATE



def build_mail_agent():
    """构建邮件代理。

    参数:
        无

    返回值:
        Agent: 邮件发送代理实例

    异常:
        无

    函数作用:
        创建并配置一个使用 send_email 工具的邮件发送代理。
    """
    settings = get_settings()
    model = get_model(settings)
    agent = create_agent(
        model=model,
        tools=[send_email],
        system_prompt=MAIL_SYSTEM_PROMPT,
    )
    return agent


def send(content: str, to_email: str) -> str:
    """通过邮件代理发送邮件。默认根据输入内容生成邮件内容，但如果内容明确指定直接发送原文，则不做修改；成功返回 'ok'，失败返回 'error: error_content'。

    参数:
        content: str - 邮件内容或生成依据
        to_email: str - 接收者邮箱地址

    返回值:
        str: 'ok' 如果发送成功，否则 'error: ...'

    异常:
        可能抛出代理调用相关的异常

    函数作用:
        使用构建的邮件代理处理并发送邮件请求。
    """
    agent = build_mail_agent()
    prompt = MAIL_USER_PROMPT_TEMPLATE.format(to_email=to_email, content=content)
    result: Any = agent.invoke({"messages": [{"role": "user", "content": prompt}]})

    if isinstance(result, dict):
        return (
            result.get("output")
            or result.get("final_output")
            or result.get("structured_response")
            or str(result)
        )
    return str(result)