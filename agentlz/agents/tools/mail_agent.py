from typing import Any

from mcp.server.fastmcp import FastMCP
from agentlz.config.settings import get_settings
from agentlz.core.model_factory import get_model
from agentlz.tools.email import send_email
from agentlz.prompts.tools.mail_prompt import MAIL_SYSTEM_PROMPT, MAIL_USER_PROMPT_TEMPLATE

# Agent: Mail Agent
def get_mail_agent():
    """
    构建并返回一个 Mail Agent。

    该 Agent 接收邮件内容和目标邮箱地址，返回发送结果。
    """
    settings = get_settings()
    model = get_model(settings)

    # 将系统提示词内置到 Agent 的调用中，避免每次显式传入
    class _MailAgentWithSystem:
        def __init__(self, base_model):
            self._base = base_model

        def invoke(self, input_data):
            # 期望输入为 {"messages": [...]}；若没有 messages，则仅注入 system 提示
            if isinstance(input_data, dict):
                messages = input_data.get("messages") or []
                # 若首条不是指定的 system 提示，则在最前面注入
                if not messages or messages[0].get("role") != "system" or messages[0].get("content") != MAIL_SYSTEM_PROMPT:
                    messages = [{"role": "system", "content": MAIL_SYSTEM_PROMPT}] + messages
                new_input = dict(input_data, messages=messages)
            else:
                # 非预期输入类型时，包装为仅包含系统提示的对话
                new_input = {"messages": [{"role": "system", "content": MAIL_SYSTEM_PROMPT}]}

            return self._base.invoke(new_input)

    return _MailAgentWithSystem(model)


mcp = FastMCP("Mail_Agent_Mcp")
@mcp.tool()
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
    mail_agent = get_mail_agent()
    prompt = MAIL_USER_PROMPT_TEMPLATE.format(to_email=to_email, content=content)
    result: Any = mail_agent.invoke({"messages": [
        {"role": "user", "content": prompt}]})

    if isinstance(result, dict):
        return (
            result.get("output")
            or result.get("final_output")
            or result.get("structured_response")
            or str(result)
        )
    return str(result)

if __name__ == "__main__":
    print("[DEBUG] 即将以 stdio 模式启动 FastMCP……")
    mcp.run(transport="stdio")

