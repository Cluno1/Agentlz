"""Check MCP Agents 可信度表。

每项示例结构：
{
  "id": "checker_mcp_1",
  "trust": 90,
  "endpoint": "stdio://...",
}

默认空表：无可用 check agent。
"""

from typing import Any, Dict, List


CHECK_AGENTS: List[Dict[str, Any]] = []