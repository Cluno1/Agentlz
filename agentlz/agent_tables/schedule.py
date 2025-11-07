"""Schedule MCP Agents 可信度表（可选）。

用于总调度自身的不同实现版本的选择（例如 schedule_1、schedule_2）。
本最小实现暂不使用；保留占位以便后续扩展。
"""

from typing import Any, Dict, List


SCHEDULE_AGENTS: List[Dict[str, Any]] = []