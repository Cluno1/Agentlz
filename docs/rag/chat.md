# 任务书
  
**现状流程（你项目里真实在跑的）**
- 入口：[agent_chat_service](file:///e:/python/agent/Agentlz/agentlz/services/agent_service.py#L932-L941)  
  - 调 [agent_chat_get_rag](file:///e:/python/agent/Agentlz/agentlz/services/rag/rag_service.py#L431-L633) 拿 doc/history/message/record_id
  - 直接把 out 丢给 [agent_llm_answer_stream](file:///e:/python/agent/Agentlz/agentlz/services/agent_service.py#L653-L772) 流式生成 output
- 持久化（异步）：[persist_chat_to_cache_and_mq](file:///e:/python/agent/Agentlz/agentlz/services/agent_service.py#L625-L650)  
  - Redis 只是写一个 `record:{agent_id}:{record_id}:{ts}:{sid}` 的 KV（不是“最近50条历史 list”）
  - 发 MQ `chat_persist_tasks`
  - MQ 消费者在 [MQService._process_chat_persist_message](file:///e:/python/agent/Agentlz/agentlz/services/mq_service.py#L164-L223) 里把 input/output 插入 MySQL `session` 表（zip 字段当前写的是 session_id 字符串，不是“压缩摘要”）
- 历史读取（给 RAG 用）：[check_session_for_rag](file:///e:/python/agent/Agentlz/agentlz/services/rag/rag_service.py#L218-L356)  
  - 先 MySQL 拉全量 sessions，再 Redis `scan_iter("record:*:{rid}:*")` 拼增量；没有 trim=50；scan 在高并发会越来越慢  
  - zip 字段基本永远是空字符串（系统没生成 zip）

---

## **MySQL 现状（必须按 init_mysql.sql 对齐）**
- 当前初始化脚本：[init_mysql.sql](file:///e:/python/agent/Agentlz/docs/deploy/sql/init_mysql.sql)
- `record` 表：`id(bigint AUTO_INCREMENT)`, `agent_id`, `name`, `meta(longtext)`, `created_at`（见 [init_mysql.sql:L164-L180](file:///e:/python/agent/Agentlz/docs/deploy/sql/init_mysql.sql#L164-L180)）
- `session` 表：`id(bigint AUTO_INCREMENT)`, `record_id`, `count`, `meta_input/ meta_output(longtext)`, `zip(longtext)`, `created_at`（见 [init_mysql.sql:L205-L220](file:///e:/python/agent/Agentlz/docs/deploy/sql/init_mysql.sql#L205-L220)）
- 关键现实约束：
  - 现在并不存在 `session.request_id` / `zip_status` 字段，`session.id` 也不是 varchar 幂等键
  - 现在 `zip` 在 MQ 落库路径里写入的是 `session_id=redis_key`（见 [mq_service.py:L164-L223](file:///e:/python/agent/Agentlz/agentlz/services/mq_service.py#L164-L223)），所以语义与“摘要 zip”冲突

**你要升级的目标（对照你给的 mermaid）**
- 你要把“串行/幂等、zip 重试幂等、上下文对 zip 缺失容错”补齐，核心变化是：  
  1) **请求路径同步落库**（至少要同步写入 `meta_input/meta_output` + `zip_status=pending`），不能继续依赖 `chat_persist_tasks` 的异步落库，否则锁释放/顺序都不成立  
  2) Redis 不再 scan KV，而是维护 **record_id 维度的 history 缓存（trim 50）**  
  3) 引入 **Zip Worker（LLM-2）** 队列与幂等更新

---

查看我项目: `e:\python\agent\Agentlz\agentlz\services\agent_service.py` 的agent_chat_service流程. 我想升级成: flowchart TD
  A[客户端调用 /chat<br/>record_id, input] --> L[Redis 加锁 record_id<br/>SET NX PX]
  L --> M{加锁成功?}
  M -->|否| N[返回: 正在处理中/重试]
  M -->|是| B{Redis 是否有该 record_id 最近50条历史?}

  B -->|有| C[从 Redis 读取历史]
  B -->|没有| D[从 MySQL 读取最近50条历史]
  D --> E[写入 Redis 历史缓存(list)<br/>并 trim 到50条]
  C --> F[组装上下文]

  E --> F
  F --> G[调用 LLM-1 生成 output]
  G --> H[写 MySQL: 插入 input/output<br/>zip 为空或zip_status=pending]
  H --> I[更新 Redis 历史缓存<br/>追加本轮 input/output<br/>trim 到50]
  I --> J[发布 MQ: zip 生成任务<br/>携带 record_row_id 或 request_id]
  J --> K[释放 Redis 锁]
  K --> R[返回 output]

  subgraph W[Zip Worker]
    Q[消费 MQ 任务] --> S[调用 LLM-2 生成 zip]
    S --> T[更新 MySQL: 写入 zip<br/>幂等: 已有zip则跳过]
    T --> U[更新 Redis: 补齐该条 zip 或追加摘要结构]
  end;

----


## **任务流程书（逐步指导改代码：每一步改哪里、改什么、验收什么）**

### 1) Redis 记录锁（record_id 串行 + 幂等入口）
**改动点**
- 在 [agent_chat_service](file:///e:/python/agent/Agentlz/agentlz/services/agent_service.py#L932-L941) 外围加“获取锁/释放锁”的包装生成器。
- 在 [cache_service.py](file:///e:/python/agent/Agentlz/agentlz/services/cache_service.py) 增加 2 个能力：`acquire_lock(record_id, ttl_ms)`、`release_lock(record_id, token)`（release 用 Lua 校验 token，避免误删别人锁）。

**实现要点**
- lock key：`chat:lock:record:{record_id}`
- value：`request_id`（优先从 meta 取 `meta["request_id"]`，没有则服务端生成 UUID）
- 加锁：`SET key value NX PX ttl_ms`
- 解锁：Lua `if get(key)==value then del(key) end`

**返回行为（对应你图里的 N）**
- 加锁失败：直接返回“正在处理中/请重试”（SSE 里立即 `data: ...` + `data: [DONE]`），不要进入 LLM。

**验收标准**
- 同一个 record_id 并发 2 个请求：只有 1 个会真正调用 LLM；另一个立刻返回重试提示。
- 人为中断第一个 SSE 连接（close/exception）：锁必须被 finally 释放，不要等 TTL。
- 运行：`python -m test.rag.record.test_lock_serialization`

---

### 2) Redis 历史缓存从“scan KV”升级为“50条 list/索引结构”
你图里要求“最近50条历史(list) + trim”，且 worker 需要能“补齐某条 zip”。单纯 list 存 JSON 会导致“更新某一条 zip 要改 list 中间元素”，不好做。建议结构化成 **list + hash**，同时满足 trim=50 和按条更新：

**Redis 结构（建议）**
- `chat:history:{record_id}:ids`（list，按时间从旧到新：RPUSH）
- `chat:history:{record_id}:map`（hash，field=session_id(bigint)，value=JSON：{count,input,output,zip,zip_status,created_at}）
- 可选：`chat:history:{record_id}:meta`（hash，存 last_count/last_id/version）

**改动点**
- 把 [check_session_for_rag](file:///e:/python/agent/Agentlz/agentlz/services/rag/rag_service.py#L218-L356) 的 Redis 部分替换为：
  - 先 `LRANGE ids -50 -1`，`HMGET map <ids...>` 组装历史
  - miss（ids 不存在或 HMGET 太少）→ 走 MySQL 拉最近 50，回填 Redis（RPUSH ids + HSET map + LTRIM + 对被 trim 的 old ids 做 HDEL）
- 禁止再使用 `scan_iter("record:*:{rid}:*")` 这种 KV 扫描（当前实现见 [rag_service.py:L247-L255](file:///e:/python/agent/Agentlz/agentlz/services/rag/rag_service.py#L247-L255)）。

**验收标准**
- Redis 不再出现 `scan_iter("record:*:{rid}:*")`
- 历史永远最多 50 条，且顺序稳定
- 冷启动（Redis 为空）时会从 MySQL 回填 Redis（ids+map），下次请求不再查全量 session
- 运行：`python -m test.rag.record.test_history_cache`

---

### 3) MySQL：同步写入 input/output + zip_pending（替代 chat_persist_tasks）
你当前的持久化是：请求结束 → 写 Redis KV → 发 MQ → MQ 再写 MySQL。这个会破坏你想要的“锁内顺序 + 幂等”。

**改动点**
- 在 [agent_llm_answer_stream](file:///e:/python/agent/Agentlz/agentlz/services/agent_service.py#L653-L772) 结束处，把 `persist_chat_to_cache_and_mq(...)` 改为 **同步写 MySQL session**，并返回 `session_id(bigint)` 与 `count`。
- 在 [session_repository.py](file:///e:/python/agent/Agentlz/agentlz/repositories/session_repository.py) 增加：
  - `get_last_count(record_id)`（SELECT MAX(count)）
  - `list_last_sessions(record_id, limit=50)`（ORDER BY count DESC, id DESC LIMIT 50）
  - `create_session_idempotent(...)`（用 request_id 做幂等插入；返回已存在或新插入的 session 行）
  - `get_session_by_id(session_id)`（Zip Worker 读取用）
  - `update_session_zip_if_pending(session_id, zip_text, zip_status)`（幂等更新用）

**表结构（强烈建议做一次升级）**
- 因为 init_mysql.sql 里 `session.id` 是 bigint 自增主键（见 [init_mysql.sql:L205-L220](file:///e:/python/agent/Agentlz/docs/deploy/sql/init_mysql.sql#L205-L220)），所以幂等键必须新增字段：
  - `request_id` varchar(64) NOT NULL（唯一索引，作为“本次请求的幂等键”）
  - `zip_status` varchar(16) NOT NULL DEFAULT 'pending'（pending/done/failed）
  - `zip_updated_at` datetime NULL
- 建议补齐索引：
  - `uk_session_request_id(request_id)`
  - `idx_session_record_count(record_id, count)`
- 建议迁移 SQL（以线上已有库为准调整）：
  - `ALTER TABLE session ADD COLUMN request_id varchar(64) NOT NULL;`
  - `ALTER TABLE session ADD COLUMN zip_status varchar(16) NOT NULL DEFAULT 'pending';`
  - `ALTER TABLE session ADD COLUMN zip_updated_at datetime NULL;`
  - `CREATE UNIQUE INDEX uk_session_request_id ON session(request_id);`
  - `CREATE INDEX idx_session_record_count ON session(record_id, count);`
  (这里修改表语句 docs\deploy\sql\init_mysql.sql , 让 程序员去进行修改表)

**幂等插入策略**
- 若同 request_id 重试：直接查出已存在的 session 行并返回（不重复插入、不重复 enqueue）。

**验收标准**
- /chat 返回前，MySQL 已经能查到本轮 session 行（meta_input/meta_output 已写入，zip_status=pending，request_id 已写入且唯一）。
- `count` 递增不依赖 `SELECT *` 全量拉取（用 `MAX(count)` 或 `ORDER BY count DESC LIMIT 1`）。
- 运行：`python -m test.rag.record.test_sync_persist_contracts`

---

### 4) 请求路径内：写 Redis 历史缓存（追加本轮并 trim=50, 结束 redis锁）
**改动点**
- 同步落库成功后，立即更新 Redis：
  - `RPUSH ids session_id`
  - `HSET map session_id <json>`
  - `LTRIM ids -50 -1`，并把被 trim 掉的 old ids 做 `HDEL`（避免 hash 膨胀）

**验收标准**
- 刚完成一轮对话后，不查 MySQL 也能从 Redis 拿到最新一条 input/output（且最多 50 条）。
- Redis 的历史缓存必须按 `record_id` 维度隔离（不同 record_id 互不影响）。
- 运行：`python -m test.rag.record.test_history_cache`

---

### 5) 发布 Zip 任务到 MQ（与 chat_persist_tasks 分离）
**改动点**
- 在同步插入 session 后，发布一个新队列消息，例如 `zip_tasks`：
  - payload：`{session_id, record_id, agent_id, request_id}`
- 在 [MQService](file:///e:/python/agent/Agentlz/agentlz/services/mq_service.py#L25-L245)：
  - `queue_declare('zip_tasks')`
  - 新增 `_process_zip_task`（仿照你现有 retry header 机制）

**验收标准**
- 每条 session 插入后都会产生一条 zip_tasks 消息（同 request_id 不重复发）。
- 保留 `chat_persist_tasks` 仅用于兼容旧路径；新主链路不再依赖它落库。

---

### 6) Zip Worker：LLM-2 生成 zip + 失败重试 + 幂等更新
**改动点**
- 在 `_process_zip_task` 中：
  1) 读 MySQL session 行（by session_id）
  2) 若 `zip_status=done` 或 zip 非空：直接 ack（幂等）
  3) 调 LLM-2 生成 zip（建议独立 prompt：把 input/output 压成短摘要）
  4) `UPDATE session SET zip=:zip, zip_status='done', zip_updated_at=NOW() WHERE id=:id AND zip_status!='done'`
  5) 更新 Redis：`HSET chat:history:{record_id}:map {session_id} <json_with_zip>`（只补齐，不改 list）

**失败重试**
- 系统异常：走你现成的 `x-retry` 重投逻辑
- 业务异常（缺行/缺字段）：直接 ack + 死信记录（避免无限重试）

**验收标准**
- zip_tasks 重复投递不会重复生成/重复覆盖 done 结果
- zip 生成失败会按 max_retries 重试，最终进入死信（可观测）
- zip 写入成功后，Redis 的 history map 对应条目的 zip/zip_status 会被补齐
- 运行：`python -m test.rag.record.test_zip_worker_idempotency`

---

### 7) 上下文组装策略：对 zip 缺失的容错（你标准里的第 3 点）
**改动点**
- 在 RAG/回答组装 history 文本的位置（当前在 [agent_chat_get_rag](file:///e:/python/agent/Agentlz/agentlz/services/rag/rag_service.py#L431-L633) 里用 `his_joined`，其来源是 `check_session_for_rag`）：
  - 约定策略：最近 K 轮用原文 input/output；更早的优先用 zip；zip 缺失则跳过或用极短截断（不要把缺失当异常）
- 这样 zip 生成慢/失败也不影响主链路回答。

**验收标准**
- zip 全空时仍能正常回答（只是上下文更短）
- zip 部分存在时，上下文 token 明显下降且质量不崩
- 运行：`python -m test.rag.record.test_history_assembly_tolerant`

---

### 8) 收尾：释放锁必须放在“生成器 finally”
**改动点**
- 由于你是 SSE Iterator，必须保证：
  - 正常结束、异常、客户端断开 都会释放锁  
- 做法是在 agent_chat_service 里用 wrapper generator：`try: yield from ... finally: release_lock(...)`

**验收标准**
- 人为打断连接后，锁不会卡死到 TTL（能被及时释放）。
- 运行：`python -m test.rag.record.test_lock_serialization`

---

## 你现在代码里“该动的关键文件清单”
- 请求主链路： [agent_service.py](file:///e:/python/agent/Agentlz/agentlz/services/agent_service.py#L625-L772)（持久化逻辑从异步改同步 + enqueue zip）
- 历史读取： [rag_service.py:check_session_for_rag](file:///e:/python/agent/Agentlz/agentlz/services/rag/rag_service.py#L218-L356)（scan→list/hash，trim=50，fallback mysql）
- MySQL 仓储： [session_repository.py](file:///e:/python/agent/Agentlz/agentlz/repositories/session_repository.py)（补“last50、maxcount、幂等插入、幂等更新zip”）
- MQ worker： [mq_service.py](file:///e:/python/agent/Agentlz/agentlz/services/mq_service.py#L25-L245)（新增 zip_tasks consumer + retry/幂等）
- Redis 工具： [cache_service.py](file:///e:/python/agent/Agentlz/agentlz/services/cache_service.py)（补 lock + list/hash 操作封装）

---

如果你接下来希望我“按这个任务流程书”带着你一段段落到代码层面，我会从第 1 步开始：先把 record_id 锁的 wrapper generator 落在 agent_chat_service，并给出每次改动的对比预览，让你逐步 Review & Accept 应用到项目里。
