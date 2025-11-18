import os
import sys
import json
from langchain_core.messages import HumanMessage
from mcp.server.fastmcp import FastMCP
from langchain.agents import create_agent

# 环境变量由 settings.py 统一管理，这里仅做引用
# 确保脚本方式运行时可定位到项目根包（提升到仓库根目录）
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agentlz.config.settings import get_settings
from agentlz.core.model_factory import get_model

# 创建MCP服务器
mcp = FastMCP("LanguageAgent")

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

language_stats = {
    "total_requests": 0,
    "last_input": "",
    "last_output": ""
}

@mcp.tool()
async def language(num: str) -> str:
    """将数字结果转化为有趣双关的描述 - 添加追踪"""
    language_stats["total_requests"] = _increment_counter("language_calls")
    language_stats["last_input"] = num
    print(f" [LanguageAgent] 开始语言处理，输入: {num}")
    try:
        settings = get_settings()
        model = get_model(settings)
        if model is None:
            return "语言处理错误: 模型未配置，请在 .env 设置 OPENAI_API_KEY 或 CHATOPENAI_API_KEY/CHATOPENAI_BASE_URL"
        system_prompt = """
          你是一个双关专家。将数学结果转化为有趣、生动的故事。
          专注于创意表达和语言润色。
          """
        agent = create_agent(model, [], system_prompt=system_prompt)
        prompt = f"""
          请将这些数字结果转化为一段有趣的话: {num}
          要求:
          1. 创作一个简短有趣的故事
          2. 包含数字的变换过程
          3. 结尾要有寓意或感悟
          4. 语言生动有趣
          """
        result = await agent.ainvoke({
            "messages": [HumanMessage(content=prompt)]
        })
        output = result["messages"][-1].content
        language_stats["last_output"] = output[:200] + "..." if len(output) > 200 else output
        print(f"[LanguageAgent] 输出: {output}")
        print(f"[LanguageAgent] 语言处理完成，输出长度: {len(output)}")
        _record_io("language", num, output)
        return output
    except Exception as e:
        print(f" [LanguageAgent] 语言处理失败: {e}")
        return f"语言处理错误: {str(e)}"

@mcp.tool()
async def get_language_stats() -> dict:
    """获取语言处理统计"""
    return language_stats

if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding='utf-8')
    mcp.run(transport="stdio")