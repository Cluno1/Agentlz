"""Tools MCP Agents 可信度表。

每项示例结构：
{
  "id": "tool_mcp_1",
  "trust": 85,
  "endpoint": "stdio://...",
  "capabilities": ["search", "markdown", "weather"]  # 可选
}

默认空表：无可用 tools agent。
"""

from typing import Any, Dict, List


TOOLS_AGENTS: List[Dict[str, Any]] = []