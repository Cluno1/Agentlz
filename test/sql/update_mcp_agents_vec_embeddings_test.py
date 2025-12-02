import sys
from contextlib import closing
from agentlz.core.database import get_pg_conn
from agentlz.core.embedding_model_factory import get_hf_embeddings


def _to_vector_literal(vec):
    return "[" + ",".join(str(float(x)) for x in vec) + "]"


def _build_text(category, description):
    a = str(category or "").strip()
    b = str(description or "").strip()
    return (a + " " + b).strip()


def main():
    try:
        emb = get_hf_embeddings()
        updated = 0
        with closing(get_pg_conn()) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name, transport, command, description, category FROM mcp_agents_vec WHERE embedding IS NULL ORDER BY id")
                rows = cur.fetchall()
                for r in rows:
                    _id = int(r[0])
                    desc = r[4]
                    cat = r[5]
                    text = _build_text(cat, desc)
                    if not text:
                        continue
                    vec = emb.embed_query(text)
                    v = _to_vector_literal(vec)
                    cur.execute("UPDATE mcp_agents_vec SET embedding=%s::vector WHERE id=%s", (v, _id))
                    updated += 1
            conn.commit()
        print("updated_count:", updated)
        sys.exit(0)
    except Exception as e:
        print("error:", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
