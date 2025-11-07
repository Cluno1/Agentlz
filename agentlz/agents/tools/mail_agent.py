from typing import Any

from langchain.agents import create_agent

from agentlz.config.settings import get_settings
from agentlz.core.model_factory import get_model
from agentlz.tools.email import send_email

MAIL_SYSTEM_PROMPT = """你是一个邮件助手。接收用户的内容与收件人地址。
当需要发送邮件时，调用工具 send_email(content, to_email)。
成功返回 'ok'，失败返回 'error: ...'。"""


def build_mail_agent():
    settings = get_settings()
    model = get_model(settings)
    agent = create_agent(
        model=model,
        tools=[send_email],
        system_prompt=MAIL_SYSTEM_PROMPT,
    )
    return agent


def send(content: str, to_email: str) -> str:
    """Send email via mail agent . default will generate email content based on the input content, but if the content explicitly specifies to send the original content directly, it will send the original content without any modification; default return 'ok' if the email is sent successfully, or 'error: error_content' if the email is not sent successfully."""
    agent = build_mail_agent()
    prompt = f"请发送邮件到 {to_email}，内容是：\n{content}\n. 默认需要根据上面内容生成邮件内容,可以修饰和扩充,但是如果上面内容明确说明直接(direct)发送原文,就只需要直接发送原文,无需添加任何额外的内容。如果无特殊说明,请直接返回 ok 或 error:error_content."
    result: Any = agent.invoke({"messages": [{"role": "user", "content": prompt}]})

    if isinstance(result, dict):
        return (
            result.get("output")
            or result.get("final_output")
            or result.get("structured_response")
            or str(result)
        )
    return str(result)