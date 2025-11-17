from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from agentlz.core.model_factory import get_model
from agentlz.config.settings import get_settings
from agentlz.prompts.check.check import CHECK_SYSTEM_PROMPT
from agentlz.schemas.check import CheckInput, CheckOutput
from mcp.server.fastmcp import FastMCP

# Agent: Check Agent
def get_check_agent() -> Runnable[CheckInput, CheckOutput]:
    """
    构建并返回一个 Check Agent。

    该 Agent 接收一个 CheckInput 对象，返回一个 CheckOutput 对象。
    它使用 LLM 来判断 factMsg 是否成功实现了 objectMsg 的目标。
    """
    # 1. 获取模型，并绑定输出结构
    settings = get_settings()
    llm = get_model(settings)
    structured_llm = llm.with_structured_output(CheckOutput)

    # 2. 创建提示词模板
    prompt = ChatPromptTemplate.from_messages([
        ("system", CHECK_SYSTEM_PROMPT),
        ("human", "目标 (Object):\n```\n{objectMsg}\n```\n\n事实 (Fact):\n```\n{factMsg}\n```"),
    ])

    # 3. 构建 LCEL 链
    #    输入格式为 {"objectMsg": "...", "factMsg": "..."}
    #    这会自动映射到 CheckInput 模型
    chain = prompt | structured_llm

    return chain

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

    
    check_agent = get_check_agent()
    # 将 Pydantic 输入转换为字典，满足 ChatPromptTemplate 的映射输入要求
    result = check_agent.invoke(check_input.model_dump())
    return result

if __name__ == "__main__":
    print("[DEBUG] 即将以 streamable-http 模式启动 FastMCP……")
    mcp.run(transport="stdio")

