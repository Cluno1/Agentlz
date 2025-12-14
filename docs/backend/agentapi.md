# 智能体管理 API 文档（/v1）

本文档描述智能体（Agent）的增删改查与 MCP 关联管理接口，覆盖列表、详情、创建、更新、删除，以及允许/排除/重置 MCP 配置。

- 路由前缀：`/v1`
- 多租户：必须在请求头携带租户标识 `X-Tenant-ID`（或 `.env` 中的 `TENANT_ID_HEADER`，默认 `X-Tenant-ID`）
- 认证：在请求头携带 `Authorization: Bearer <token>`

## 获取 Token

```
curl -s -X POST \
  -H "X-Tenant-ID: default" \
  -H "Content-Type: application/json" \
  -d '{
        "username": "admin",
        "password": "admin"
      }' \
  http://localhost:8000/v1/login
```

## 公共请求头
- `Authorization: Bearer <token>`
- `X-Tenant-ID: <your-tenant>`（当接口按租户隔离时必须）
- `Content-Type: application/json`（POST/PUT 请求）

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

## 1) 列表查询：GET /v1/agents
- 说明：分页查询智能体列表。
- 查询参数：
  - `page`: 整数，默认 1
  - `per_page`: 整数，默认 10，范围 1-100
  - `sort`: 字段，默认 `id`（白名单映射）
  - `order`: `ASC|DESC`，默认 `DESC`
  - `q`: 可选，名称关键词（不传则不筛选）
  - `type`: `self|tenant`（`self` 仅本人 default 租户；`tenant` 当前租户）
- 示例：
```
curl -s "http://localhost:8000/v1/agents?type=tenant&page=1&per_page=10" \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: t_acme"
```

### 参数规格
- 格式: 启用,参数名,参数值,类型,必需,说明
- 参数
  true,type,tenant,string,true,type=self|tenant（self 仅本人 default 租户tenant 当前租户）
  true,page,1,int,false,页码默认 1
  true,per_page,10,int,false,每页条数默认 10范围 1-100
  true,sort,id,string,false,排序字段白名单（见 agentlz/repositories/agent_repository.py:26-38）
  true,order,DESC,string,false,排序方向（ASC|DESC）默认 DESC
  true,q,,string,false,名称关键词（不传则不筛选）
- 请求头
  true,Authorization,Bearer <token>,string,true,
  true,X-Tenant-ID,t_acme,string,true,

## 2) 单条查询：GET /v1/agents/{agent_id}
- 说明：获取智能体详情。
- 示例：
```
curl -s "http://localhost:8000/v1/agents/123" \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: t_acme"
```

### 参数规格
- 格式: 启用,参数名,参数值,类型,必需,说明
- 参数
  - `true,agent_id,123,int,true,路径参数（智能体ID）`
- 请求头
  - `Authorization:Bearer <token>`
  - `X-Tenant-ID:t_acme`

## 3) 创建：POST /v1/agents?type=self|tenant
- 说明：创建智能体；`type=self` 写入 default 租户，`type=tenant` 写入当前租户。
- 请求体 (`AgentCreate`)：
```
{
  "name": "代码助手",
  "description": "用于代码相关",
  "disabled": false,
  "mcp_agent_ids": [1,2],
  "document_ids": ["DOC123"]
}
```
- 示例（租户写入）：
```
curl -s -X POST "http://localhost:8000/v1/agents?type=tenant" \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: t_acme" \
  -H "Content-Type: application/json" \
  -d '{"name":"团队工具","description":"租户私有"}'
```
- 示例（个人 default）：
```
curl -s -X POST "http://localhost:8000/v1/agents?type=self" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name":"我的助手","description":"个人"}'
```

### 参数规格
- 格式: 启用,参数名,参数值,类型,必需,说明
- 参数
  - `true,type,tenant,string,true,type=self|tenant（self 写入 default，tenant 写入当前租户）`
- 请求头
  - `Authorization:Bearer <token>`
  - `X-Tenant-ID:t_acme`（当 `type=tenant`）

## 4) 更新基本信息：PUT /v1/agents/{agent_id}
- 说明：更新名称/描述/禁用，以及关联的文档与 MCP ID 列表。
- 请求体 (`AgentUpdate`)：
```
{
  "name": "新名称",
  "description": "新描述",
  "disabled": false,
  "mcp_agent_ids": [3,4],
  "document_ids": ["DOC999"]
}
```
- 示例：
```
curl -s -X PUT "http://localhost:8000/v1/agents/123" \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: t_acme" \
  -H "Content-Type: application/json" \
  -d '{"name":"新名称","description":"新描述","disabled":false}'
```

### 参数规格
- 格式: 启用,参数名,参数值,类型,必需,说明
- 参数
  - `true,agent_id,123,int,true,路径参数（智能体ID）`
- 请求头
  - `Authorization:Bearer <token>`
  - `X-Tenant-ID:t_acme`

## 5) 更新 API 密钥：PUT /v1/agents/{agent_id}/api
- 说明：更新 `api_name` 与 `api_key`（返回时不回显密钥）。
- 请求体 (`AgentApiUpdate`)：
```
{ "api_name": "openai", "api_key": "sk-xxx" }
```
- 示例：
```
curl -s -X PUT "http://localhost:8000/v1/agents/123/api" \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: t_acme" \
  -H "Content-Type: application/json" \
  -d '{"api_name":"openai","api_key":"sk-xxx"}'
```

### 参数规格
- 格式: 启用,参数名,参数值,类型,必需,说明
- 参数
  - `true,agent_id,123,int,true,路径参数（智能体ID）`
- 请求头
  - `Authorization:Bearer <token>`
  - `X-Tenant-ID:t_acme`

## 6) 删除：DELETE /v1/agents/{agent_id}
- 示例：
```
curl -s -X DELETE "http://localhost:8000/v1/agents/123" \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: t_acme"
```

### 参数规格
- 格式: 启用,参数名,参数值,类型,必需,说明
- 参数
  - `true,agent_id,123,int,true,路径参数（智能体ID）`
- 请求头
  - `Authorization:Bearer <token>`
  - `X-Tenant-ID:t_acme`

## 7) ：PUT /v1/agents/{agent_id}/mcp/allow
- 说明：覆盖原有设置，保存允许集。
- 请求体：
```
{ "mcp_agent_ids": [23,45] }
```
- 示例：
```
curl -s -X PUT "http://localhost:8000/v1/agents/123/mcp/allow" \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: t_acme" \
  -H "Content-Type: application/json" \
  -d '{"mcp_agent_ids":[23,45]}'
```

### 参数规格
- 格式: 启用,参数名,参数值,类型,必需,说明
- 参数
  - `true,agent_id,123,int,true,路径参数（智能体ID）`
- 请求头
  - `Authorization:Bearer <token>`
  - `X-Tenant-ID:t_acme`

## 8) 设置排除的 MCP 列表：PUT /v1/agents/{agent_id}/mcp/exclude
- 说明：增量排除；依赖 `agent_mcp` 表存在列 `permission_type`/`is_default`。
- 请求体：
```
{ "mcp_agent_ids": [23,45] }
```
- 示例：
```
curl -s -X PUT "http://localhost:8000/v1/agents/123/mcp/exclude" \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: t_acme" \
  -H "Content-Type: application/json" \
  -d '{"mcp_agent_ids":[23,45]}'
```

### 参数规格
- 格式: 启用,参数名,参数值,类型,必需,说明
- 参数
  - `true,agent_id,123,int,true,路径参数（智能体ID）`
- 请求头
  - `Authorization:Bearer <token>`
  - `X-Tenant-ID:t_acme`

## 9) 恢复默认 MCP 配置：DELETE /v1/agents/{agent_id}/mcp/reset
- 说明：清空 `agent_mcp` 关系，恢复全量可用。
- 示例：
```
curl -s -X DELETE "http://localhost:8000/v1/agents/123/mcp/reset" \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: t_acme"
```

### 参数规格
- 格式: 启用,参数名,参数值,类型,必需,说明
- 参数
  - `true,agent_id,123,int,true,路径参数（智能体ID）`
- 请求头
  - `Authorization:Bearer <token>`
  - `X-Tenant-ID:t_acme`

## 权限说明
- 需要登录认证（`Authorization`）。
- 访问/更新权限规则：
  - 创建者直接允许。
  - 管理员：当用户租户等于 agent 租户，且该租户不为 `default` 时允许。
  - 普通用户：`user_agent_permission` 中权限为 `admin` 或 `write` 时允许。

## 参考代码
- 路由：`agentlz/app/routers/agent.py`
- 服务：`agentlz/services/agent_service.py`
- 权限与租户头解析：`agentlz/app/deps/auth_deps.py`
- ```
  toolName: search_codebase
              
  status: success
            
  query: Find FastAPI app main entry, server port, base path for API.
            
  
          
              
  toolName: search_codebase
              
  status: success
            
  query: Find routes related to MCP search or mcp agents endpoints.
            
  
          
              
  toolName: search_codebase
              
  status: success
            
  query: Search for routers exposing MCP agents endpoints (list, create, search).
            
  
          
              
  toolName: view_files
              
  status: success
            
              
  filePath: d:\PyCharm\AgentCode\Agentlz\agentlz\app\http_langserve.py
            
  
          
              
  toolName: view_files
              
  status: success
            
              
  filePath: d:\PyCharm\AgentCode\Agentlz\agentlz\app\deps\auth_deps.py
            
  
          
              
  toolName: search_by_regex
              
  status: success
            
  query: APIRouter\(prefix="/v1", tags=\["mcp
            
  **前置要求**
  - 基础路径：`http://localhost:8000`
  - 统一前缀：`/v1`
  - 认证头：`Authorization: Bearer <token>`（通过登录获取）
  - 租户头：`X-Tenant-ID: <your-tenant>`（可在 `agentlz/app/deps/auth_deps.py:63-67` 配置，默认 `X-Tenant-ID`）
  
  **获取 Token**
  - 登录：`POST /v1/login`
  - 位置：`agentlz/app/routers/auth.py:12`
  - 请求体：`{"username":"demo","password":"demo"}`
  
  **Agent 接口**
  - 列表查询：`GET /v1/agents?type=self|tenant&page=1&per_page=10&sort=id&order=DESC&q=关键字`
    - 位置：`agentlz/app/routers/agent.py:17`
    - 说明：`type=self` 返回“个人(default租户，创建者本人)”，`type=tenant` 返回当前租户下的智能体
  - 单条查询：`GET /v1/agents/{agent_id}`
    - 位置：`agentlz/app/routers/agent.py:48`
  - 创建：`POST /v1/agents?type=self|tenant`
    - 位置：`agentlz/app/routers/agent.py:62`
    - 请求体示例：`{"name":"代码助手","description":"用于代码相关","mcp_agent_ids":[1,2],"document_ids":["DOC123"]}`
    - 说明：`type=self` 写入 default 租户；`type=tenant` 按 `X-Tenant-ID` 写入
  - 更新基本信息：`PUT /v1/agents/{agent_id}`
    - 位置：`agentlz/app/routers/agent.py:79`
    - 请求体示例：`{"name":"新名称","description":"新描述","disabled":false,"mcp_agent_ids":[3,4],"document_ids":["DOC999"]}`
  - 更新 API 密钥：`PUT /v1/agents/{agent_id}/api`
    - 位置：`agentlz/app/routers/agent.py:93`
    - 请求体示例：`{"api_name":"openai","api_key":"******"}`
  - 删除：`DELETE /v1/agents/{agent_id}`
    - 位置：`agentlz/app/routers/agent.py:113`
  - 设置允许的 MCP 列表：`PUT /v1/agents/{agent_id}/mcp/allow`
    - 位置：`agentlz/app/routers/agent.py:126`
    - 请求体示例：`{"mcp_agent_ids":[23,45]}`
  - 设置排除的 MCP 列表：`PUT /v1/agents/{agent_id}/mcp/exclude`
    - 位置：`agentlz/app/routers/agent.py:146`
    - 请求体示例：`{"mcp_agent_ids":[23,45]}`
  - 恢复默认 MCP 配置：`DELETE /v1/agents/{agent_id}/mcp/reset`
    - 位置：`agentlz/app/routers/agent.py:166`
  
  **链路接口（使用 MCP 检索）**
  - 流式对话（Planner 会调用 `search_mcp` 工具，内部使用 `search_mcp_agents_service`）：`GET /v1/chat?user_input=你的需求`
    - 位置：`agentlz/app/routers/chain.py:10`
    - 说明：需携带 `X-Tenant-ID` 与 `Authorization`；当前检索可见集为“共享 ∪ 传入租户 ∪ 个人”，由 `agentlz/services/mcp_service.py:115` 联动 `agentlz/repositories/mcp_repository.py:76-92`
  
  **示例请求**
  - 列表（当前租户）：
    - `GET http://localhost:8000/v1/agents?type=tenant&page=1&per_page=10`
    - 头：`Authorization: Bearer <token>`、`X-Tenant-ID: t_acme`
  - 创建（default 个人）：
    - `POST http://localhost:8000/v1/agents?type=self`
    - 头：`Authorization: Bearer <token>`
    - 体：`{"name":"代码助手","description":"用于代码相关"}`
  - 创建（指定租户）：
    - `POST http://localhost:8000/v1/agents?type=tenant`
    - 头：`Authorization: Bearer <token>`、`X-Tenant-ID: t_acme`
    - 体：`{"name":"团队工具","description":"租户私有"}`
  - 允许集：
    - `PUT http://localhost:8000/v1/agents/123/mcp/allow`
    - 体：`{"mcp_agent_ids":[23,45]}`
  - 排除集：
    - `PUT http://localhost:8000/v1/agents/123/mcp/exclude`
    - 体：`{"mcp_agent_ids":[23,45]}`
  - 重置：
    - `DELETE http://localhost:8000/v1/agents/123/mcp/reset`
  - 链路（触发 MCP 检索）：
    - `GET http://localhost:8000/v1/chat?user_input=查找“PDF解析”工具`
    - 头：`Authorization: Bearer <token>`、`X-Tenant-ID: t_acme`
  
  **提示**
  - `tenant_id` 的来源为请求头 `X-Tenant-ID`，解析位置：`agentlz/app/deps/auth_deps.py:62-67`
  - `search_mcp_agents_service` 为服务方法，不直接暴露 HTTP 接口；通过 Planner 的工具 `search_mcp` 间接触发，入口在链路接口。
  ```

  
