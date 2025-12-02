import sys
import os

from agentlz.core.database import get_pg_engine
from agentlz.config.settings import get_settings
from agentlz.core.embedding_model_factory import get_hf_embeddings
from agentlz.repositories.pg_mcp_repository import upsert_mcp_agent_vector


def main():
    try:
        pg = get_pg_engine()
        with pg.connect() as conn:
            conn = conn.execution_options(autocommit=True)
            ver = conn.exec_driver_sql("SELECT version()").scalar()
            ext_cnt = conn.exec_driver_sql("SELECT COUNT(*) FROM pg_extension WHERE extname='vector'").scalar()
            table_reg = conn.exec_driver_sql("SELECT to_regclass('public.mcp_agents_vec')").scalar()
            print(f"pg_version={ver} vector_ext_installed={int(ext_cnt or 0)} table_exists={bool(table_reg)}")
            conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector;")
            if table_reg is not None:
                conn.exec_driver_sql("ALTER TABLE mcp_agents_vec ADD COLUMN IF NOT EXISTS embedding VECTOR(1536);")

            row = conn.exec_driver_sql(
                "SELECT id, name, transport, command, description, category FROM mcp_agents_vec ORDER BY id ASC LIMIT %s",
                (1,),
            ).mappings().first()
            if not row:
                print("no_rows")
                sys.exit(2)

            fast = any(a in ("--fast", "fast") for a in sys.argv[1:]) or os.getenv("FAST_EMB") == "1"
            print(f"mode={'fast' if fast else 'full'}")
            settings = get_settings()
            name = settings.hf_embedding_model or "BAAI/bge-small-zh-v1.5"
            src = "local" if os.path.isdir(name) else "hub"
            print(f"embedding_model={name} source={src} device=cpu target_dim=1536")
            text = f"{row.get('description','')} {row.get('category','')}".strip()
            if fast:
                vec = [0.0] * 1536
            else:
                emb = get_hf_embeddings()
                vec = emb.embed_query(text) if text else [0.0] * 1536

            upsert_mcp_agent_vector(
                agent_id=int(row.get("id")),
                name=row.get("name") or "",
                transport=row.get("transport") or "",
                command=row.get("command") or "",
                description=row.get("description") or "",
                category=row.get("category") or "",
                embedding=vec,
            )

            out = conn.exec_driver_sql(
                "SELECT embedding::text FROM mcp_agents_vec WHERE id=%s",
                (int(row.get("id")),),
            ).fetchone()
            print(f"updated_id={int(row.get('id'))} emb={out[0] if out else None}")
            sys.exit(0)
    except Exception as e:
        print("error:", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
