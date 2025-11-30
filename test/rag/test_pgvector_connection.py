import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"   # ✅
import json
import hashlib
import random

from agentlz.services.mcp_service import (
    create_mcp_agent_service,
    search_mcp_agents_service,
)
from agentlz.repositories.pg_mcp_repository import upsert_mcp_agent_vector
from agentlz.repositories.mcp_repository import get_mcp_agents_by_unique
from agentlz.core.embedding_model_factory import get_hf_embeddings
from agentlz.config.settings import get_settings


def main():
    s = get_settings()
    print("pg url:", s.pgvector_url or f"postgresql://{s.pgvector_user}:{s.pgvector_password}@{s.pgvector_host}:{s.pgvector_port}/{s.pgvector_db}")

    payload = {
        "name": "exa_remote",
        "transport": "http",
        "command": "npx",
        "args": ["-y", "mcp-remote", "https://mcp.exa.ai/mcp"],
        "description": "Exa github代码搜索远端 MCP 服务",
        "category": "tool",
        "trust_score": 85,
    }

    agent_id = None
    try:
        row = create_mcp_agent_service(payload)
        agent_id = int(row.get("id"))
        print("inserted:", json.dumps(row, ensure_ascii=False))
    except Exception as e:
        print("insert error:", repr(e))
        try:
            rows = get_mcp_agents_by_unique([(payload["name"], payload["transport"], payload["command"])])
            if rows:
                agent_id = int(rows[0].get("id"))
                print("found existing id:", agent_id)
        except Exception:
            pass

    # 构造语义文本
    text = (payload.get("description") or "") + " " + (payload.get("category") or "")
    vec = None
    # 优先使用本地模型路径，存在则加载；否则跳过直接走随机向量回退
    model_path = s.hf_embedding_model
    if isinstance(model_path, str) and model_path and os.path.isdir(model_path):
        try:
            emb = get_hf_embeddings(model_name=model_path)
            vec = emb.embed_query(text.strip())
        except Exception:
            vec = None
    if vec is None:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        seed = int.from_bytes(h[:8], "big")
        rnd = random.Random(seed)
        vec = [rnd.random() for _ in range(512)]

    if agent_id is not None and vec is not None:
        try:
            upsert_mcp_agent_vector(
                agent_id,
                payload["name"],
                payload["transport"],
                payload["command"],
                payload.get("description") or "",
                payload.get("category") or "",
                vec,
            )
            print(json.dumps({"event": "emb.upsert", "id": agent_id, "dim": len(vec)}, ensure_ascii=False))
        except Exception as e:
            print("emb upsert error:", repr(e))

    try:
        rows = search_mcp_agents_service("github 代码 搜索", k=3)
        print("search count:", len(rows))
        for r in rows:
            print(json.dumps(r, ensure_ascii=False))
    except Exception as e:
        print("search skipped:", repr(e))


if __name__ == "__main__":
    main()
