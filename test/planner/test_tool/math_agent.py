import os
import sys
import json
import time
from langchain_core.messages import HumanMessage
from mcp.server.fastmcp import FastMCP
from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
# 确保脚本方式运行时可定位到项目根包（提升到仓库根目录）
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agentlz.config.settings import get_settings
from agentlz.core.model_factory import get_model
from test.planner.test_tool import math_tool

# 创建MCP服务器
mcp = FastMCP("MathAgent")
call_stack = []
tool_usage_count = {}
COUNTER_JSON_PATH = r"d:\PyCharm\AgentCode\Agentlz\test\planner\counter.json"

def _increment_counter(key: str) -> int:
    try:
        with open(COUNTER_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    value = int(data.get(key, 0)) + 1
    data[key] = value
    try:
        with open(COUNTER_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass
    return value


def _record_io(prefix: str, input_val: str, output_val: str) -> None:
    try:
        with open(COUNTER_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    data[f"{prefix}_last_input"] = input_val
    data[f"{prefix}_last_output"] = output_val
    logs_key = f"{prefix}_logs"
    logs = data.get(logs_key)
    if not isinstance(logs, list):
        logs = []
    logs.append({"input": input_val, "output": output_val})
    data[logs_key] = logs
    try:
        with open(COUNTER_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass

_math_tool_path = os.path.abspath(math_tool.__file__)
math_client = MultiServerMCPClient({
    "math_mcp": {
        "transport": "stdio",
        # 使用当前解释器，确保处于相同虚拟环境
        "command": sys.executable,
        "args": [_math_tool_path]
    }
})

@mcp.tool()
async def calculate(expression: str) -> str:
    """计算数学表达式 - 添加详细追踪"""
    call_id = f"calculate_{int(time.time() * 1000)}"
    call_stack.append({"id": call_id, "tool": "calculate", "input": expression, "timestamp": time.time()})
    try:
        tool_usage_count["calculate"] = tool_usage_count.get("calculate", 0) + 1
        _increment_counter("math_calls")
        tools = await math_client.get_tools()
        print(f"🛠️  获取到 {len(tools)} 个数学工具")
        settings = get_settings()
        model = get_model(settings)
        if model is None:
            return "计算错误: 模型未配置，请在 .env 设置 OPENAI_API_KEY 或 CHATOPENAI_API_KEY/CHATOPENAI_BASE_URL"
        system_prompt = """
        你是一个数学专家。将复杂问题分解为简单步骤，每次调用一个数学工具。
        请详细记录你的思考过程。
        """
        agent = create_agent(model, tools, system_prompt=system_prompt)
        result = await agent.ainvoke({
            "messages": [HumanMessage(content=f"计算: {expression}")]
        })
        final_result = result["messages"][-1].content
        print(f"✅ [MathAgent] 计算完成: {final_result[:100]}...")
        _record_io("math", expression, final_result)
        return final_result
    except Exception as e:
        print(f"❌ [MathAgent] 执行失败: {e}")
        return f"计算错误: {str(e)}"
    finally:
        call_stack.pop()
        print(f"🏁 [MathAgent] 调用完成，剩余调用栈: {len(call_stack)})")

@mcp.tool()
async def get_execution_stats() -> dict:
    """获取执行统计信息"""
    return {
        "total_calls": sum(tool_usage_count.values()),
        "tool_usage": tool_usage_count,
        "current_stack_depth": len(call_stack),
        "call_stack": call_stack[-5:]
    }

if __name__ == "__main__":
    if sys.platform == "win32":
        # 避免 Windows 控制台编码导致 stdio 传输异常
        sys.stdout.reconfigure(encoding='utf-8')
    print("🚀 MathAgent MCP服务器启动...")
    mcp.run(transport="stdio")