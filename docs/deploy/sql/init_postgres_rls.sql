-- Active: 1763648474172@@117.72.162.89@5432@agentlz
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunk_embeddings (
    chunk_id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    doc_id VARCHAR(64) NOT NULL,
    embedding VECTOR(1536) NOT NULL,
    content TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 为分块向量创建索引 在 chunk_embeddings 上创建一个复合 B-Tree 索引，用于加速按租户和文档筛选、关联。
--  常见查询如 WHERE tenant_id = :tenant_id AND doc_id = :doc_id 会显著加速。
CREATE INDEX IF NOT EXISTS idx_ce_tenant_doc ON chunk_embeddings (tenant_id, doc_id);


-- 启行级安全，使该表只能访问符合策略的行。
ALTER TABLE chunk_embeddings ENABLE ROW LEVEL SECURITY;

-- 先删除同名策略，保证脚本可重复执行。
DROP POLICY IF EXISTS tenant_isolate ON chunk_embeddings;

-- 创建策略，限制只能访问当前租户的数据。
--  FOR ALL 表示对所有操作（SELECT, INSERT, UPDATE, DELETE）应用策略。
--  USING 子句定义了筛选条件，只有符合条件的行才会被访问。
--  WITH CHECK 子句定义了插入或更新时的检查条件，确保只有符合条件的行才会被修改。
CREATE POLICY tenant_isolate ON chunk_embeddings
  FOR ALL
  USING (tenant_id = current_setting('app.current_tenant', true)::varchar)
  WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::varchar);

-- 建 ivfflat 索引通常在数据批量导入后再创建，效果更好；查询前可 ANALYZE chunk_embeddings; 提升计划质量。

--  创建 pgvector 的近似向量检索索引，类型为 ivfflat ，距离度量为欧氏距离（L2）。
--  lists = 100 控制索引的倒排列表数量，影响速度/召回率的权衡；查询时可用 SET ivfflat.probes = N; 调整检索精度（如 10、20、50）。 

CREATE INDEX IF NOT EXISTS idx_ce_embedding_l2
  ON chunk_embeddings USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);