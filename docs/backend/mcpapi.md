# MCP 管理 API 文档（/v1）

本文档描述 MCP（Model Context Protocol）工具的管理与检索相关接口，覆盖：上传私有 MCP、设为共享、可见池混合搜索。接口遵循多租户与认证约定，与 Agent 选配接口相互配合。

- 路由前缀：`/v1`
- 多租户：请求头携带 `X-Tenant-ID`（或 `.env` 中的 `TENANT_ID_HEADER`，默认 `X-Tenant-ID`）
- 认证：`Authorization: Bearer <token>`

## 响应结构
统一返回 `Result`：

```
{
  "success": true,
  "code": 0,
  "message": "ok",
  "data": { /* 实际数据 */ }
}
```

## 1) 上传私有 MCP：POST /v1/mcp
- 说明：上传 MCP 工具定义到 MySQL；写入 `tenant_id='default'`，`created_by_id=当前用户ID`；幂等：唯一键冲突时返回已有行并保持向量；同步 PG 向量以支持检索。
- 请求体（示例）：
```
{
  "name": "PDF_Parser",
  "transport": "stdio",
  "command": "python",
  "args": ["-m","pdf_tool"],
  "description": "解析并抽取 PDF 文本内容",
  "category": "document",
  "trust_score": 60.5
}
```
- 示例：
```
curl -s -X POST "http://localhost:8000/v1/mcp" \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: default" \
  -H "Content-Type: application/json" \
  -d '{
        "name":"PDF_Parser",
        "transport":"stdio",
        "command":"python",
        "args":["-m","pdf_tool"],
        "description":"解析并抽取 PDF 文本内容",
        "category":"document",
        "trust_score":60.5
      }'
```

### 参数规格
- 格式: 启用,参数名,参数值,类型,必需,说明
- 参数
  - `true,name,PDF_Parser,string,true,工具名称（唯一键的一部分）`
  - `true,transport,stdio,string,true,传输方式（如 stdio、http）`
  - `true,command,python,string,true,启动命令`
  - `true,args,["-m","pdf_tool"],array,false,命令参数（JSON 数组或字符串）`
  - `true,description,解析 PDF,text,true,工具描述`
  - `true,category,document,string,false,分类标签`
  - `true,trust_score,60.5,double,false,可信度得分（0-100）`
- 请求头
  - `Authorization: Bearer <token>`
  - `X-Tenant-ID: default`

## 1.1) 上传租户级 MCP：POST /v1/mcp?type=tenant
- 说明：上传到当前租户私有池（`tenant_id=请求头 X-Tenant-ID`），记录 `created_by_id=当前用户ID`。适用于租户范围内共享但不跨租户的 MCP。
- 权限：建议仅管理员可上传到租户级（与用户管理一致）。
- 请求体（与私有上传一致）。
- 示例：
```
curl -s -X POST "http://localhost:8000/v1/mcp?type=tenant" \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: t_acme" \
  -H "Content-Type: application/json" \
  -d '{
        "name":"PDF_Parser（tenant）",
        "transport":"stdio",
        "command":"python",
        "args":["-m","pdf_tool"],
        "description":"解析并抽取 PDF 文本内容",
        "category":"document",
        "trust_score":60.5
      }'
```

### 参数规格
- 格式: 启用,参数名,参数值,类型,必需,说明
- 参数
  - `true,type,tenant,string,true,上传目标：self|tenant（tenant 为当前租户）`
- 请求头
  - `Authorization: Bearer <token>`
  - `X-Tenant-ID: t_acme`

## 2) 上传共享 MCP：所有人都可以上传
- 说明：直接上传到共享池（`tenant_id='system'`），任何已登录用户均可上传；请求体与“上传私有 MCP”一致。
- 示例：
```
curl -s -X POST "http://localhost:8000/v1/mcp?type=system" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
        "name":"PDF_Parser",
        "transport":"stdio",
        "command":"python",
        "args":["-m","pdf_tool"],
        "description":"解析并抽取 PDF 文本内容",
        "category":"document",
        "trust_score":60.5
      }'
```

### 参数规格
- 格式: 启用,参数名,参数值,类型,必需,说明
- 参数
  - `true,type,system,string,true,上传目标：system（共享池）`
- 请求头
  - `Authorization: Bearer <token>`

## 3) 根据关键词搜索 MCP：GET /v1/mcp/search
- 说明：先在 MySQL 计算可见集合（共享 `system` ∪ 个人 `default/created_by_id=本人`），可选融合 Agent 选配差量（ALLOW/EXCLUDE），再在 PG 上进行语义/可信度混合排序，并返回 Top‑k。
- 示例：
```
curl -s "http://localhost:8000/v1/mcp/search?q=PDF&k=5" \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: t_acme"
```
- 可选按 Agent 选配差量：
```
curl -s "http://localhost:8000/v1/mcp/search?q=PDF&k=5&agent_id=123" \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: t_acme"
```

### 参数规格
- 格式: 启用,参数名,参数值,类型,必需,说明
- 参数
  - `true,q,PDF,string,true,查询关键词`
  - `true,k,5,int,false,Top‑k 返回数量（默认 10）`
  - `true,agent_id,123,int,false,Agent ID（融合允许/排除差量）`
  - `true,alpha,0.7,float,false,融合权重（语义占比）`
  - `true,theta,0.75,float,false,语义门槛（过滤低相关）`
  - `true,N,50,int,false,候选集合大小`
- 请求头
  - `Authorization: Bearer <token>`
  - `X-Tenant-ID: <your-tenant>`

## 4) 列表查询：GET /v1/mcp
- 说明：按范围列出 MCP（个人 self 或租户 tenant），支持分页/排序/搜索。
- 示例：
```
curl -s "http://localhost:8000/v1/mcp?type=self&page=1&per_page=10&sort=id&order=DESC&q=PDF" \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: t_acme"
```

### 参数规格
- 格式: 启用,参数名,参数值,类型,必需,说明
- 参数
  - `true,type,self,string,true,范围：self|tenant|system`
  - `true,page,1,int,false,页码（默认 1）`
  - `true,per_page,10,int,false,每页数量（默认 10，最大 100）`
  - `true,sort,id,string,false,排序字段（id|name|trust_score）`
  - `true,order,DESC,string,false,排序方向（ASC|DESC）`
  - `true,q,PDF,string,false,按名称模糊搜索`
- 请求头
  - `Authorization: Bearer <token>`
  - `X-Tenant-ID: <your-tenant>`

## 5) 查询详情：GET /v1/mcp/{id}
- 说明：返回单个 MCP；可见性规则：共享 `system` ∪ 当前租户 `tenant_id` ∪ 个人 `default/created_by_id=本人`。
- 示例：
```
curl -s "http://localhost:8000/v1/mcp/162" \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: t_acme"
```

### 参数规格
- 格式: 启用,参数名,参数值,类型,必需,说明
- 参数
  - `true,id,162,int,true,路径参数（MCP 工具ID）`
- 请求头
  - `Authorization: Bearer <token>`
  - `X-Tenant-ID: <your-tenant>`

## 6) 更新 MCP：PUT /v1/mcp/{id}
- 说明：创建者或管理员（同租户，非 `default`）可更新。若变更 `description/category/transport/command` 会重新嵌入并 UPSERT PG；变更 `trust_score` 将同步 PG 可信度。
- 请求体（示例）：
```
{ "description": "新的描述", "category": "document", "trust_score": 75 }
```
- 示例：
```
curl -s -X PUT "http://localhost:8000/v1/mcp/162" \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: t_acme" \
  -H "Content-Type: application/json" \
  -d '{"description":"新的描述","category":"document","trust_score":75}'
```

### 参数规格
- 格式: 启用,参数名,参数值,类型,必需,说明
- 参数
  - `true,id,162,int,true,路径参数（MCP 工具ID）`
  - `true,name,PDF_Parser,string,false,工具名称`
  - `true,transport,stdio,string,false,传输方式`
  - `true,command,python,string,false,启动命令`
  - `true,args,["-m","pdf_tool"],array,false,命令参数（JSON 数组或字符串）`
  - `true,description,解析 PDF,text,false,工具描述（变更触发向量同步）`
  - `true,category,document,string,false,分类标签（变更触发向量同步）`
  - `true,trust_score,75,double,false,可信度（变更同步 PG）`
- 请求头
  - `Authorization: Bearer <token>`
  - `X-Tenant-ID: <your-tenant>`

## 7) 删除 MCP：DELETE /v1/mcp/{id}
- 说明：创建者或管理员（同租户，非 `default`）可删除；同时删除 PG 向量并清理 Agent‑MCP 关联。
- 示例：
```
curl -s -X DELETE "http://localhost:8000/v1/mcp/162" \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: t_acme"
```

### 参数规格
- 格式: 启用,参数名,参数值,类型,必需,说明
- 参数
  - `true,id,162,int,true,路径参数（MCP 工具ID）`
- 请求头
  - `Authorization: Bearer <token>`
  - `X-Tenant-ID: <your-tenant>`

## 权限说明
- 需要登录认证（`Authorization`）。
- 上传：默认写入个人池（`tenant_id='default'`）；租户级上传需管理员。
- 共享上传：`type=system` 所有已登录用户可上传到共享池（`tenant_id='system'`）。
- 更新/删除：创建者或管理员（同租户，非 `default`）。
- 搜索：共享池 `system` ∪ 个人池 `default/created_by_id=本人`；如传入 `agent_id`，对可见集应用 Agent 的允许/排除差量。

## 参考代码
- 服务：
  - `agentlz/services/mcp_service.py:65` 创建（幂等 + 向量/可信度写入）
  - `agentlz/services/mcp_service.py:103` 更新并同步向量/可信度
  - `agentlz/services/mcp_service.py:131` 列表（self/tenant）
  - `agentlz/services/mcp_service.py:153` 详情与可见性校验
  - `agentlz/services/mcp_service.py:165` 更新鉴权包装
  - `agentlz/services/mcp_service.py:176` 删除（PG 向量 + Agent 关联清理）
  - `agentlz/services/mcp_service.py:199` 混合搜索（语义/可信度融合）
- 路由：
  - `agentlz/app/routers/mcp.py:11` 创建 MCP（`POST /v1/mcp`）
  - `agentlz/app/routers/mcp.py:31` 列表（`GET /v1/mcp`）
  - `agentlz/app/routers/mcp.py:48` 详情（`GET /v1/mcp/{id}`）
  - `agentlz/app/routers/mcp.py:56` 更新（`PUT /v1/mcp/{id}`）
  - `agentlz/app/routers/mcp.py:64` 删除（`DELETE /v1/mcp/{id}`）
  - `agentlz/app/routers/mcp.py:81` 搜索（`GET /v1/mcp/search`）
- PostgreSQL：
  - `agentlz/repositories/pg_mcp_repository.py:42` 向量 UPSERT `upsert_mcp_agent_vector`
  - `agentlz/repositories/pg_mcp_repository.py:75` 候选限制与混合排序 `search_mcp_hybrid_pg`
  - `agentlz/repositories/pg_mcp_repository.py:138` 更新可信度 `update_trust_score_pg`
  - `agentlz/repositories/pg_mcp_repository.py:146` 删除向量 `delete_mcp_agent_vector`
- MySQL：
  - `agentlz/repositories/mcp_repository.py:51` `get_mcp_agents_by_ids`
  - `agentlz/repositories/mcp_repository.py:115` `list_agent_mcp_allow_ids`
  - `agentlz/repositories/mcp_repository.py:126` `list_agent_mcp_exclude_ids`
  - `agentlz/repositories/mcp_repository.py:138` `get_mcp_agents_by_unique`
  - `agentlz/repositories/mcp_repository.py:329` `list_mcp_self`
  - `agentlz/repositories/mcp_repository.py:359` `list_mcp_tenant`
  - `agentlz/repositories/mcp_repository.py:389` `delete_mcp_agent`
- 关联清理：
  - `agentlz/repositories/agent_mcp_repository.py:181` `clear_agent_mcp_by_mcp_id`

---

提示：本文件描述 MCP 管理与检索接口的设计与用法；与 Agent 选配接口（`PUT /v1/agents/{agent_id}/mcp/allow|exclude|reset`）配套使用，相关内容见 `docs/backend/agentapi.md`。
