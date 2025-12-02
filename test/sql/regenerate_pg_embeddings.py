import sys

from agentlz.core.database import get_pg_engine
from agentlz.core.embedding_model_factory import get_hf_embeddings
from agentlz.repositories.pg_mcp_repository import upsert_mcp_agent_vector


def main():
    try:
        pg = get_pg_engine()
        with pg.connect() as conn:
            conn = conn.execution_options(autocommit=True)
            conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector;")
            conn.exec_driver_sql("ALTER TABLE mcp_agents_vec ADD COLUMN IF NOT EXISTS embedding VECTOR(1536);")

            emb = get_hf_embeddings()

            rows = conn.exec_driver_sql(
                "SELECT id, name, transport, command, description, category FROM mcp_agents_vec ORDER BY id ASC",
            ).mappings().all()

            updated = 0
            first_id = None
            for r in rows:
                text = f"{r.get('description','')} {r.get('category','')}".strip()
                vec = emb.embed_query(text) if text else []
                upsert_mcp_agent_vector(
                    agent_id=int(r.get("id")),
                    name=r.get("name") or "",
                    transport=r.get("transport") or "",
                    command=r.get("command") or "",
                    description=r.get("description") or "",
                    category=r.get("category") or "",
                    embedding=vec if vec else [0.0] * 1536,
                )
                if first_id is None:
                    first_id = int(r.get("id"))
                updated += 1

            first_emb = None
            if first_id is not None:
                row = conn.exec_driver_sql(
                    "SELECT embedding::text FROM mcp_agents_vec WHERE id=%s",
                    (first_id,),
                ).fetchone()
                first_emb = row[0] if row else None

            print(f"regenerated_embeddings={updated} first_id={first_id} first_emb={first_emb}")
            sys.exit(0)
    except Exception as e:
        print("error:", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
