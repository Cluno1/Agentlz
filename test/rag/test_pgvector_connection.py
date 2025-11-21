import os
import json

from agentlz.services.mcp_service import (
    create_mcp_agent_service,
    search_mcp_agents_service,
)


def main():
    print("！！！PGVECTOR_URL=", os.getenv("PGVECTOR_URL"))
    payload = {
        "name": "exa_remote",
        "transport": "http",
        "command": "npx",
        "args": ["-y", "mcp-remote", "https://mcp.exa.ai/mcp"],
        "description": "Exa github代码搜索远端 MCP 服务",
        "category": "tool",
        "trust_score": 85,
    }

    try:
        row = create_mcp_agent_service(payload)
        print("inserted:", json.dumps(row, ensure_ascii=False))
    except Exception as e:
        print("insert error:", repr(e))

    try:
        rows = search_mcp_agents_service("github 代码 搜索", k=3)
        print("search count:", len(rows))
        for r in rows:
            print(json.dumps(r, ensure_ascii=False))
    except Exception as e:
        print("search error:", repr(e))


if __name__ == "__main__":
    main()