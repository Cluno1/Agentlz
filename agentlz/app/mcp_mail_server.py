import asyncio
import logging

from mcp.server.fastmcp import FastMCP

from ..agents.mail_agent import send as mail_send
from ..core.logger import setup_logging
from ..config.settings import get_settings


# 初始化日志（MCP STDIO 不应使用 print，日志写到 stderr 即可）
settings = get_settings()
logger = setup_logging(settings.log_level)

# 创建 MCP 服务端
mcp = FastMCP(name="agentlz-mail")


@mcp.tool(
    name="mail.send",
    description="使用 Agentlz 邮件代理发送邮件。入参：content、to_email；返回 'ok' 或 'error: ...'",
)
def mcp_send_mail(content: str, to_email: str) -> str:
    """发送邮件（通过 Agentlz 的 mail_agent)。

    Args:
        content: 邮件正文或提示；若包含 direct 指令则原文发送
        to_email: 收件人邮箱地址

    Returns:
        'ok' 或 'error: ...'
    """
    logger.info(f"MCP tool mail.send invoked: to={to_email}")
    return mail_send(content, to_email)


if __name__ == "__main__":
    # 以 STDIO 方式运行 MCP 服务端
    # 注意：不要使用 print 输出，否则会破坏 STDIO JSON-RPC 通信
    asyncio.run(mcp.run())