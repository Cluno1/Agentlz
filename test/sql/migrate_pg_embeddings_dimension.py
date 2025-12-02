import sys
from typing import List

from agentlz.core.database import get_pg_engine, get_mysql_engine
from agentlz.core.embedding_model_factory import get_hf_embeddings
from agentlz.repositories.pg_mcp_repository import upsert_mcp_agent_vector, update_trust_score_pg


def fetch_mysql_rows(limit: int = 50) -> List[dict]:
    eng = get_mysql_engine()
    with eng.connect() as conn:
        rows = conn.exec_driver_sql(
            "SELECT id,name,transport,command,description,category,trust_score FROM mcp_agents ORDER BY id ASC LIMIT %s",
            (int(limit),),
        ).mappings().all()
    return [dict(r) for r in rows]


def ensure_pg_column_dim(dim: int) -> None:
    pg = get_pg_engine()
    with pg.connect() as conn:
        conn = conn.execution_options(autocommit=True)
        conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector;")
        exists = conn.exec_driver_sql("SELECT to_regclass('public.mcp_agents_vec')").scalar()
        if exists is None:
            conn.exec_driver_sql(
                f"CREATE TABLE mcp_agents_vec (id BIGINT PRIMARY KEY, name TEXT, transport TEXT, command TEXT, description TEXT, category TEXT, embedding VECTOR({dim}), trust_score REAL DEFAULT 0);"
            )
        try:
            conn.exec_driver_sql("ALTER TABLE mcp_agents_vec ADD COLUMN IF NOT EXISTS embedding_new VECTOR(%s)" % int(dim))
        except Exception:
            pass
        try:
            conn.exec_driver_sql("DROP INDEX IF EXISTS idx_mcp_agents_vec_embedding;")
        except Exception:
            pass
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_mcp_agents_vec_embedding ON mcp_agents_vec USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);"
        )
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_mcp_agents_name_tr_cmd ON mcp_agents_vec (name, transport, command);"
        )


def main():
    try:
        target_dim = 1536
        ensure_pg_column_dim(target_dim)
        emb = get_hf_embeddings()
        rows = fetch_mysql_rows(limit=50)
        updated = 0
        pg = get_pg_engine()
        with pg.connect() as conn:
            conn = conn.execution_options(autocommit=True)
            for r in rows:
                text = f"{r.get('description','')} {r.get('category','')}".strip()
                vec = emb.embed_query(text)
                conn.exec_driver_sql(
                    "INSERT INTO mcp_agents_vec (id, name, transport, command, description, category, trust_score) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, transport=EXCLUDED.transport, command=EXCLUDED.command, description=EXCLUDED.description, category=EXCLUDED.category, trust_score=EXCLUDED.trust_score",
                    (
                        int(r.get("id")),
                        r.get("name") or "",
                        r.get("transport") or "",
                        r.get("command") or "",
                        r.get("description") or "",
                        r.get("category") or "",
                        float(r.get("trust_score", 0) or 0),
                    ),
                )
                conn.exec_driver_sql(
                    "UPDATE mcp_agents_vec SET embedding_new=%s::vector WHERE id=%s",
                    ("[" + ",".join(str(float(x)) for x in vec) + "]", int(r.get("id"))),
                )
                updated += 1
            try:
                conn.exec_driver_sql("DROP INDEX IF EXISTS idx_mcp_agents_vec_embedding;")
            except Exception:
                pass
            conn.exec_driver_sql("ALTER TABLE mcp_agents_vec DROP COLUMN embedding;")
            conn.exec_driver_sql("ALTER TABLE mcp_agents_vec RENAME COLUMN embedding_new TO embedding;")
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS idx_mcp_agents_vec_embedding ON mcp_agents_vec USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);"
            )
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_mcp_agents_name_tr_cmd ON mcp_agents_vec (name, transport, command);"
            )
        print(f"migrated_embeddings={updated} target_dim={target_dim}")
        sys.exit(0)
    except Exception as e:
        print("error:", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()

