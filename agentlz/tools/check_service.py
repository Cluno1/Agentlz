from mcp.server.fastmcp import FastMCP
from agentlz.agents.check.check_agent_1 import get_check_agent
from agentlz.schemas.check import CheckInput, CheckOutput

mcp = FastMCP("Check_Base")


@mcp.tool()
def check(check_input: CheckInput) -> CheckOutput:
    """
    检查 factMsg 是否实现了 objectMsg。

    此函数评估提供的 factMsg 是否准确且完整地满足 objectMsg 中描述的目标。它返回判断结果、
    质量分数和评估理由。

    参数:
    check_input (CheckInput): 包含 objectMsg 和 factMsg 的输入。

    返回:
    CheckOutput: 包含 judge (bool)、score (int) 和 reasoning (str) 的输出。
    """

    # 可以在 app 中这样调用
    check_agent = get_check_agent()
    # 将 Pydantic 输入转换为字典，满足 ChatPromptTemplate 的映射输入要求
    result = check_agent.invoke(check_input.model_dump())
    return result

if __name__ == "__main__":
    print("[DEBUG] 即将以 streamable-http 模式启动 FastMCP……")
    mcp.run(transport="streamable-http")
