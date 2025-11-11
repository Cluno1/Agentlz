from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from agentlz.core.model_factory import get_model
from agentlz.config.settings import get_settings
from agentlz.prompts.check.check import CHECK_SYSTEM_PROMPT
from agentlz.schemas.check import CheckInput, CheckOutput



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

# 可以在 app 中这样调用
# check_agent = get_check_agent()
# result = check_agent.invoke({"objectMsg": "...", "factMsg": "..."})
# print(result.judge, result.score, result.reasoning)

