目标概述

交付一个“多链路召回”的 RAG 检索层，融合 MySQL 关键词/元数据检索与 PostgreSQL/pgvector 语义检索，支持查询扩展、重排与分数融合，并对多租户与审计负责
严格遵守 docs/dev.md 与 docs/backend/layers.md 的分层与安全规范，避免跨层耦合，统一日志与响应结构
仅使用 MySQL 与 PostgreSQL（pgvector），不使用 FAISS
参考文档

数据与存储、RAG 规范见 docs/dev.md:173 与 docs/dev.md:182
分层约束见 docs/backend/layers.md:25-66
接口设计见 docs/backend_structure_and_api.md:29-68
改动目录

agentlz/repositories/：新增 mysql_docs_repository.py、pgvector_repository.py
agentlz/services/：新增 rag_service.py
agentlz/tools/retrievers/：新增 mysql_keyword.py、pgvector_semantic.py、fusion.py、expand.py、rerank.py
agentlz/schemas/：新增 rag.py
agentlz/prompts/：新增中文提示词 rag_expand.md、rag_rerank.md
agentlz/config/：如需补充 pgvector 索引/距离度量配置，在 settings.py 扩展配置项
agentlz/app/routers/（可选）：新增 rag.py 路由或在现有 /v1/agents/{agent_id}/query 中接入 rag_service（推荐路由分组）
实施步骤

设计与建模
在 schemas/rag.py 定义 RetrievalQuery、RetrievedChunk、RetrievalSource、AggregatedResult，字段含 tenant_id、query_text、top_k、filters、score、source、chunk_id、doc_id、metadata
在 config/settings.py 校验 MySQL_DB_PATH 与 POSTGRES_DSN；增加 PGVECTOR_DISTANCE、RETRIEVAL_TOPK、RRF_K 等默认值
数据访问
repositories/mysql_docs_repository.py：提供基于 MySQL 的文档/chunk 元数据读取与 FULLTEXT 检索（含 tenant_id、标签/类型过滤）
repositories/pgvector_repository.py：提供写入/查询 pgvector 的 chunk 向量；实现 SELECT ... ORDER BY embedding <=> query_embedding LIMIT :k（按 PGVECTOR_DISTANCE 切换 <=>/cosine）
工具与策略
tools/retrievers/mysql_keyword.py：实现关键词召回、标题/标签/作者/时间过滤与 BM25/TF-IDF 加权（可用 MySQL FULLTEXT）
tools/retrievers/pgvector_semantic.py：实现语义召回，统一通过 core/model_factory.py 生成查询向量
tools/retrievers/expand.py：实现 LLM 查询扩展（子查询/同义词/描述性改写），调用 prompts/rag_expand.md 并生成去重后的子查询集
tools/retrievers/rerank.py：实现 LLM 语义重排（按相关性/完整性/时效性），调用 prompts/rag_rerank.md，输出打分并可应用租户/合规过滤
tools/retrievers/fusion.py：实现分数融合（RRF、加权线性、时间衰减），含去重与源标记（source=mysql_keyword|pgvector|...）
服务编排
services/rag_service.py：提供 retrieve(query: RetrievalQuery) -> AggregatedResult
步骤：查询扩展 → 并行多通道召回（MySQL 关键词 + pgvector 语义）→ 分数标准化与融合（RRF/权重）→ LLM 重排（可选）→ 组装 AggregatedResult
严格多租户过滤（tenant_id）与审计日志写入（core/logger.py），记录 request_id/latency_ms/来源比例
超时与重试策略，对外部 I/O 设定合理超时；失败降级（仅关键词或仅语义）
接口对接
路由：在 /v1/agents/{agent_id}/query 的编排中插入 rag_service.retrieve 以实现 RAG 支持，或新增 /v1/rag/query（返回统一 AgentResponse）
输出结构：将 AggregatedResult 的 intermediate_chunks、分数与来源合并到 AgentResponse.data 的可观测字段
质量与运维
单元测试覆盖 fusion、expand、rerank、repositories 的过滤与多租户隔离
在日志与指标中记录检索耗时、每通道命中数、重排提升率、降级次数；开放 /v1/metrics
详细 Prompt（交给 LLM 执行） 你是资深后端工程师，目标是在现有 Agentlz 项目中实现“RAG 多链路召回”，仅使用 MySQL 与 PostgreSQL（pgvector），严格遵守项目文档与分层规范。请按以下要求完成实现，并输出所有新增文件的完整代码与对现有文件的最小必要修改。

总体约束

Python 3.14，所有代码带类型标注；Docstring 使用中文并遵循 Google/NumPy 风格
严格分层：app → agents/services/schemas/config/core；禁止跨层耦合
多租户与安全：所有检索必须以 tenant_id 为主过滤；不硬编码密钥；配置通过 config/settings.py
日志：使用 core/logger.py 的统一结构化日志，包含 request_id、tenant_id、latency_ms
I/O：所有数据库操作具备超时、重试与失败降级；不阻塞事件循环
不引入 FAISS，仅使用 MySQL 与 PostgreSQL（pgvector）
数据结构与配置

新增 agentlz/schemas/rag.py，定义：
RetrievalQuery（tenant_id: str、query_text: str、top_k: int = 10、filters: dict | None、enable_rerank: bool = True、enable_expand: bool = True）
RetrievedChunk（chunk_id: str、doc_id: str、text: str、metadata: dict、score: float、source: Literal["mysql_keyword","pgvector","fallback"]）
AggregatedResult（query: RetrievalQuery、chunks: list[RetrievedChunk]、stats: dict）
在 config/settings.py 扩展：
PGVECTOR_DISTANCE: Literal["cosine","euclidean"] = "cosine"
RETRIEVAL_TOPK: int = 10
RRF_K: int = 60
读取并校验 MySQL_DB_PATH 与 POSTGRES_DSN
数据访问层

新增 agentlz/repositories/mysql_docs_repository.py：
提供：search_fulltext(tenant_id, query_text, filters, top_k) -> list[RetrievedChunk]
要求：MySQL FULLTEXT（标题/正文）检索，支持标签/类型/时间窗口过滤；保证 tenant_id 隔离；返回结构含来源 mysql_keyword
新增 agentlz/repositories/pgvector_repository.py：
提供：search_vector(tenant_id, query_embedding, filters, top_k, distance) -> list[RetrievedChunk]
要求：使用 embedding <=> :query_embedding/cosine_distance 执行；按 PGVECTOR_DISTANCE 切换；返回来源 pgvector
检索工具层

新增 agentlz/tools/retrievers/mysql_keyword.py：
封装对 mysql_docs_repository 的调用，支持对分数进行标准化（0-1）
新增 agentlz/tools/retrievers/pgvector_semantic.py：
使用 core/model_factory.py 创建 Embeddings；生成查询向量并调用 pgvector_repository
新增 agentlz/tools/retrievers/expand.py：
使用中文提示词 agentlz/prompts/rag_expand.md，基于原始查询生成 3-5 个高质量子查询（同义词/缩写/补充上下文）；去重并保留语义差异
新增 agentlz/tools/retrievers/rerank.py：
使用中文提示词 agentlz/prompts/rag_rerank.md，按相关性/完整性/时效性为候选 chunk 打分重排；可在 filters 中传入时间偏好与文档类型
新增 agentlz/tools/retrievers/fusion.py：
实现 RRF：score = Σ 1/(rank_i + K) 与加权线性融合；对相同 chunk_id 去重合并；保留最强来源
服务编排层

新增 agentlz/services/rag_service.py：
提供 async def retrieve(query: RetrievalQuery) -> AggregatedResult
流程：
若 enable_expand，调用 expand 生成子查询集合；否则仅用原始查询
并行执行：MySQL 关键词检索与 pgvector 语义检索；对每个子查询取 top_k // 2；合并结果
使用 fusion 标准化与融合分数（RRF_K 可配置）；时间衰减权重可通过 filters 控制
若 enable_rerank，调用 rerank 对融合后的 TopN 进行 LLM 重排
组装 AggregatedResult，stats 包含：每通道命中数、扩展查询数、重排耗时、降级策略
日志：埋点各阶段耗时与错误，记录 request_id 与 tenant_id
降级：若 pgvector 失败，仅返回关键词检索；若 MySQL 失败，返回 pgvector；必要时返回空列表与告警
提示词文件

新增 agentlz/prompts/rag_expand.md（中文）：要求生成语义多样化的子查询，覆盖同义词/专业术语/上下位词/场景化描述；输出 JSON 数组
新增 agentlz/prompts/rag_rerank.md（中文）：给定查询与候选 chunk，按相关性、完整性、时效性打分并输出 TopN 的排序与分数（JSON）
接口集成（选其一）

在 agentlz/app/routers/rag.py 新增 POST /v1/rag/query，入参 RetrievalQuery；返回 AgentResponse（见 docs/backend_structure_and_api.md:37）
或在既有 /v1/agents/{agent_id}/query 内部调用 rag_service.retrieve，将 AggregatedResult 注入 intermediate_steps
测试与质量

为 fusion.py、expand.py、rerank.py、repositories/* 编写单元测试，覆盖多租户过滤、查询扩展去重、RRF 正确性、失败降级
在响应头加入 X-Request-ID 并暴露 /v1/metrics 的检索耗时与命中数（参考 docs/backend_structure_and_api.md:46-47, 66-67）
交付与验收

提交所有新增文件的完整实现代码与对现有文件的最小改动
运行演示：构造 tenant_id="demo" 的查询，显示融合前后分数、来源比例、重排提升率
文档同步：在代码 Docstring 中用中文解释函数作用、参数、返回值与异常
输出格式

逐文件代码块输出（新文件用完整代码块，修改现有文件时先展示原/新差异预览，再输出完整代码）
附带基本使用示例与测试用例代码块
实现要点

多链路召回的关键是“多样化输入 + 并行检索 + 统一分数空间 + 重排”，注意去重与来源标记
保持查询扩展的可控性（避免过度扩展导致噪声），建议子查询数 3–5，TopK 分配按通道均衡
RRF 对跨通道稳定有效；加权融合可用于偏好语义或关键词的场景，可通过配置调整权重
对隐私与合规敏感数据，在 rerank 与返回数据中做脱敏或遮盖；严格多租户隔离，避免数据泄露


## 总体架构
总体方案

- 文档与元数据存 MySQL 做全文检索；语义向量存 PostgreSQL pgvector 做向量检索
- 统一以 tenant_id 作为主过滤维度，所有表含 tenant_id 字段，查询严格带条件
- 检索时并行跑“关键词全文检索 + 语义向量检索”，再做分数标准化与融合，必要时用更强模型做重排
文档入库

- 划分策略
  - 按语义段落分块，建议 200–500 中文字或 256–512 token
  - 以句子边界合并，避免拆断句子；长段落用滑窗覆盖（如 20–30% overlap）
  - 每块产出 chunk_id 、 doc_id 、 tenant_id 、 text 、 position 、 title 、 tags 、 type 、 published_at
- 存储设计
  - MySQL：存文档与分块文本、元数据，建 FULLTEXT 索引于 title 、 body ；用于关键词检索
  - PostgreSQL：存每个分块的 embedding 向量与必要元数据，启用 pgvector ，用于语义检索
- 示例表结构（MySQL）
  - docs： id 、 tenant_id 、 title 、 author 、 type 、 tags(JSON) 、 published_at 、 created_at
  - chunks： chunk_id 、 tenant_id 、 doc_id 、 position 、 body(TEXT) 、 metadata(JSON) ，FULLTEXT( title , body )
```
-- MySQL
CREATE TABLE docs (
  id VARCHAR(64) PRIMARY KEY,
  tenant_id VARCHAR(64) NOT NULL,
  title VARCHAR(512),
  author VARCHAR(128),
  type VARCHAR(64),
  tags JSON,
  published_at DATETIME,
  created_at DATETIME DEFAULT 
  CURRENT_TIMESTAMP,
  KEY idx_docs_tenant (tenant_id),
  FULLTEXT KEY ft_title (title)
);

CREATE TABLE chunks (
  chunk_id VARCHAR(64) PRIMARY KEY,
  tenant_id VARCHAR(64) NOT NULL,
  doc_id VARCHAR(64) NOT NULL,
  position INT NOT NULL,
  title VARCHAR(512),
  body TEXT NOT NULL,
  metadata JSON,
  KEY idx_chunks_tenant_doc 
  (tenant_id, doc_id, position),
  FULLTEXT KEY ft_title_body 
  (title, body)
);
```
- 示例表结构（PostgreSQL）
```
CREATE EXTENSION IF NOT EXISTS 
vector;

CREATE TABLE chunk_embeddings (
  chunk_id VARCHAR(64) PRIMARY KEY,
  tenant_id VARCHAR(64) NOT NULL,
  doc_id VARCHAR(64) NOT NULL,
  embedding vector(768),
  type VARCHAR(64),
  tags JSONB,
  published_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now
  ()
);

CREATE INDEX idx_ce_tenant ON 
chunk_embeddings (tenant_id);
CREATE INDEX idx_ce_doc ON 
chunk_embeddings (doc_id);
```
- 嵌入生成与写入
  - 统一用嵌入模型将分块 body 转向量，维度与模型在配置中定义（见 e:\python\agent\Agentlz\docs\postgreSQL\readme.md:78-80, 61-65 ）
  - 批量写入 Postgres；写入失败可重试，最终保证与 MySQL 分块表 chunk_id 对齐
是否需要“关键词向量”

- 不需要。关键词检索用 MySQL FULLTEXT/Inverted Index；向量库存的是稠密语义向量
- 可选进阶：若要稀疏向量混检（如 SPLADE），需额外存“稀疏向量”；本项目不要求（ e:\python\agent\Agentlz\docs\postgreSQL\readme.md:54, 68-73 ）
租户查询与搜索

- 请求结构
  - tenant_id 必填； query_text ； top_k ； filters （ type 、 tags 、时间窗口）； enable_expand 、 enable_rerank （ e:\python\agent\Agentlz\docs\postgreSQL\readme.md:57-60 ）
- 查询扩展（可选）
  - 生成 3–5 个子查询并去重，控制语义差异（ e:\python\agent\Agentlz\docs\postgreSQL\readme.md:80-81, 121-123 ）
- 并行初检索
  - 关键词检索（MySQL）
```
SELECT c.chunk_id, c.doc_id, c.body,
       JSON_OBJECT('title', c.
       title, 'type', d.type, 
       'tags', d.tags, 
       'published_at', d.
       published_at) AS metadata,
       MATCH(c.title, c.body) 
       AGAINST (:q IN NATURAL 
       LANGUAGE MODE) AS score
FROM chunks c
JOIN docs d ON d.id = c.doc_id AND 
d.tenant_id = c.tenant_id
WHERE c.tenant_id = :tenant_id
  AND (:type IS NULL OR d.type = 
  :type)
  AND (:start IS NULL OR d.
  published_at >= :start)
  AND (:end IS NULL OR d.
  published_at <= :end)
ORDER BY score DESC
LIMIT :k;
```
- 语义检索（PostgreSQL pgvector ，度量可切换余弦/欧氏， e:\python\agent\Agentlz\docs\postgreSQL\readme.md:61-65, 71-73 ）
```
-- 余弦距离示例（需预先归一化或使用内置函
数）
SELECT chunk_id, doc_id, embedding 
<=> :query_embedding AS score, 
tags, type, published_at
FROM chunk_embeddings
WHERE tenant_id = :tenant_id
ORDER BY embedding <=> 
:query_embedding
LIMIT :k;
```
- 分数标准化与融合
  - 将 MySQL 与 pgvector 分数映射到 [0,1]（如 min-max 或 z-score）
  - RRF 融合： score = Σ 1/(rank_i + K) ， K 默认 60（ e:\python\agent\Agentlz\docs\postgreSQL\readme.md:33-34, 85, 93 ）
  - 按 chunk_id 去重合并，保留最佳来源与综合分
- 重排（可选）
  - 对融合后的 TopN 用更强模型逐条打分，指标：相关性、完整性、时效性；可用 filters 的时间偏好（ e:\python\agent\Agentlz\docs\postgreSQL\readme.md:83-84, 94 ）
- 返回结果
  - 输出 chunks 列表（含 chunk_id/doc_id/text/metadata/score/source ）与 stats （命中数、扩展数、耗时、降级信息）（ e:\python\agent\Agentlz\docs\postgreSQL\readme.md:59-60, 95 ）
多租户与安全

- 表结构含 tenant_id ；所有查询必须 WHERE tenant_id = :tenant_id
- 统一结构化日志记录 request_id/tenant_id/latency_ms 与通道命中数（ e:\python\agent\Agentlz\docs\postgreSQL\readme.md:52-53, 37 ）
- 不在日志或代码中写入密钥；配置从 settings 读取并校验（ e:\python\agent\Agentlz\docs\postgreSQL\readme.md:24, 61-65 ）
超时、重试与降级

- 外部 I/O 设置合理超时与重试；单通道失败时另一通道兜底，必要时返回空并告警（ e:\python\agent\Agentlz\docs\postgreSQL\readme.md:38, 97 ）
- TopK 分配：对子查询均衡分配到两通道（如每通道 top_k // 2 ）（ e:\python\agent\Agentlz\docs\postgreSQL\readme.md:92 ）
运营与调参建议

- 指标：每通道命中数、融合前后 nDCG/MRR、重排提升率、耗时分解、降级次数（ e:\python\agent\Agentlz\docs\postgreSQL\readme.md:42-45, 107-109 ）
- 调参： RRF_K 、各通道权重、 PGVECTOR_DISTANCE 、扩展查询数、TopN 用于重排的规模
总结：入库阶段把文本和结构化信息放 MySQL 做全文检索，把每个分块的语义向量放 Postgres pgvector ；检索阶段并行跑两通道，做标准化与 RRF 融合，必要时用强模型重排；全链路以 tenant_id 严格隔离并有完善的超时与降级策略。