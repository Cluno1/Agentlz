import sys
import math
from mcp.server.fastmcp import FastMCP

# 轻量数学 MCP 服务器：仅通过 stdio 输出协议帧，不在 stdout 打印日志
mcp = FastMCP("BasicMathTool")

ALLOWED_FUNCS = {
    "sqrt": math.sqrt,
    "pow": pow,
    "abs": abs,
    "round": round,
}

@mcp.tool()
async def evaluate(expression: str) -> str:
    """安全计算简单数学表达式，如 '1+2*3' 或 'sqrt(16)'."""
    try:
        # 禁用内建，允许的函数作为上下文
        result = eval(expression, {"__builtins__": {}}, ALLOWED_FUNCS)
        return str(result)
    except Exception as e:
        # 日志使用 stderr，避免污染 MCP stdout 协议
        print(f"[BasicMathTool] 计算失败: {e}", file=sys.stderr)
        return f"错误: {e}"

if __name__ == "__main__":
    if sys.platform == "win32":
        # 仅调整编码；不要向 stdout 打印额外文本
        sys.stdout.reconfigure(encoding="utf-8")
    mcp.run(transport="stdio")