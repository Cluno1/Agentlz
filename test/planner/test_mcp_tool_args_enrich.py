import sys
import json
import time

import agentlz.agents.planner.tools.mcp_config_tool as toolmod
from agentlz.repositories.mcp_repository import create_mcp_agent


def main():
    try:
        name = f"代码助手_{int(time.time()*1000)}"
        row = create_mcp_agent({
            "name": name,
            "transport": "stdio",
            "command": "python",
            "args": ["--foo", "bar"],
            "description": "用于代码相关的检索与解释",
            "category": "code",
            "trust_score": 55,
        })
        rid = int(row.get("id"))
        orig = toolmod.search_mcp_agents_service
        try:
            toolmod.search_mcp_agents_service = lambda *args, **kwargs: [{
                "id": rid,
                "name": name,
                "transport": "stdio",
                "command": "python",
                "description": row.get("description"),
                "category": row.get("category"),
                "trust_score": row.get("trust_score"),
                "sem_score": 0.5,
                "total_score": 0.5,
            }]
            out = toolmod.get_mcp_config_by_keyword.invoke("代码")
        finally:
            toolmod.search_mcp_agents_service = orig
        rows = json.loads(out or "[]")
        print("enriched_rows:", rows)
        assert len(rows) >= 1, "工具输出为空"
        first = rows[0]
        assert first.get("name") == name, "返回的名称不匹配"
        assert first.get("args") == ["--foo", "bar"], "未按ID从MySQL补全 args"
        print("args enrich tests passed")
        sys.exit(0)
    except Exception as e:
        print("error:", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()

