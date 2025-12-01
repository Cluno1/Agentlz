import sys
import json
import time

import agentlz.agents.planner.tools.mcp_config_tool as toolmod
from agentlz.repositories.mcp_repository import create_mcp_agent


def ensure_sample():
    name = f"代码助手_{int(time.time()*1000)}"
    row = create_mcp_agent({
        "name": name,
        "transport": "stdio",
        "command": "python",
        "args": ["--help"],
        "description": "用于代码相关的检索与解释",
        "category": "code",
        "trust_score": 60,
    })
    return row.get("name")


def main():
    try:
        ensure_sample()
        orig = toolmod.search_mcp_agents_service
        try:
            toolmod.search_mcp_agents_service = lambda *args, **kwargs: []
            out = toolmod.get_mcp_config_by_keyword.invoke("代码")
        finally:
            toolmod.search_mcp_agents_service = orig
        rows = json.loads(out or "[]")
        print("fallback_rows:", rows)
        assert len(rows) > 0, "回退到关键词检索仍为空，请检查 MySQL mcp_agents 数据"
        sys.exit(0)
    except Exception as e:
        print("error:", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()

