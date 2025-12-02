CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS public.mcp_agents_vec (
    id bigint PRIMARY KEY,
    name text,
    transport text,
    command text,
    description text,
    category text,
    trust_score real DEFAULT 0,
    embedding vector(1536)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_mcp_agents_name_tr_cmd ON public.mcp_agents_vec USING btree (name, transport, command);

ALTER TABLE public.mcp_agents_vec ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS mcp_agents_allow_all ON public.mcp_agents_vec;
CREATE POLICY mcp_agents_allow_all ON public.mcp_agents_vec FOR ALL USING (true) WITH CHECK (true);

CREATE INDEX IF NOT EXISTS idx_mcp_agents_embedding_l2 ON public.mcp_agents_vec USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);
