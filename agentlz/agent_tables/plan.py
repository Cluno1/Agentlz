"""Plan MCP Agents 可信度表。

每项示例结构：
{
  "id": "planner_mcp_1",
  "trust": 95,  # 1-100，越高优先级越高
  "endpoint": "stdio://...",  # MCP 连接信息（占位）
}

默认空表：无可用 plan agent。
"""

from typing import Any, Dict, List


PLAN_AGENTS: List[Dict[str, Any]] = []