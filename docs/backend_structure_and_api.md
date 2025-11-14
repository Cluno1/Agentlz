# Agentlz Python 后端项目结构与接口规范建议

- 目标：结合主流 Python 后端项目结构最佳实践与本仓库 `docs/dev.md` 规范，提供接口设计规范与业务代码归属建议，确保可维护、可扩展与可审计。

## 行业内主流结构综述

- FastAPI 模板：推荐按“路由/依赖/模型/服务/配置”分层，参考 Full Stack FastAPI Template（Tiangolo，含路由、依赖注入、设置管理与测试）(FastAPI — Full Stack Template: https://fastapi.tiangolo.com/project-generation/)

## 与本仓库的综合建议（对齐 docs/dev.md）

- 路由与接口层（HTTP）：
  - 建议在 `agentlz/app/` 下增加 `routers/` 目录，按领域拆分路由模块并在 `http_langserve.py` 中统一挂载。
  - 若暂不新建目录，保持在 `http_langserve.py` 中组织 `APIRouter` 亦可，但推荐模块化以提升可维护性。
- 编排与智能体：
  - `agentlz/agents/`：存放各类 Agent（planner、schedule、tools 协作等），遵循“提示词在 `prompts/`、结构在 `schemas/`”。
- 业务与领域逻辑：
  - `agentlz/services/`：承载与 LLM 无关的领域服务与业务规则（如文档索引、租户校验、审计写入、RBAC 判定）。
- 工具封装：
  - `agentlz/tools/`：`@tool` 工具与适配器（搜索、markdown、外部 API 的轻量封装）。
- 外部集成：
  - `agentlz/integrations/`：三方 API 客户端（重试/限流/断路器策略），避免直接在路由或 Agent 中调用。
- 横切能力：
  - `agentlz/core/`：日志、错误、重试、并发、模型工厂等基础设施；
  - `agentlz/config/`：统一 `.env` 与设置验证（Pydantic Settings）。
- 数据结构与提示词：
  - `agentlz/schemas/`：Pydantic 模型（请求/响应/错误结构）；
  - `agentlz/prompts/`：中文提示词模板，按 Agent 分类管理。

## 接口规范（REST / WebSocket，对齐 `/v1` 前缀）

- 版本与路径：
  - 所有路由以 `/v1` 为前缀；建议为将来兼容预留 `/v2` 并通过“路由分组 + tag”管理。
- 鉴权与多租户：
  - `Authorization: Bearer <JWT>` 必填；
  - `X-Tenant-ID` 头标识租户，后端需在每次请求做租户隔离与权限校验。
- 统一响应体：
  - 使用 `AgentResponse`（参见 `agentlz/schemas/responses.py`），包含 `request_id`、`data` 或 `error`；
  - 失败统一以 `error.code`、`error.message`、`error.details` 表达，并映射为准确的 HTTP 状态码。
- 幂等与速率限制：
  - 支持 `Idempotency-Key` 请求头，服务端对相同键进行去重；
  - 返回 `X-RateLimit-*` 相关响应头；对滥用行为记录审计与告警。
- 请求/响应建模：
  - 全量通过 Pydantic 模型进行校验与文档生成；字段命名统一使用 `snake_case`；
  - 大对象上传使用 `multipart/form-data`；流式响应采用 SSE/WebSocket。
- 追踪与可观测：
  - 日志为结构化 JSON，包含 `timestamp`、`level`、`request_id`、`tenant_id`、`agent_id`、`latency_ms`；
  - 建议在响应头加入 `X-Request-ID`，并接入 OpenTelemetry 进行分布式追踪。
- API 文档：
  - OpenAPI 文档通过 FastAPI 自动生成，按路由 tag 分组；在 `/docs` 与 `/openapi.json` 暴露；
  - 为关键 DTO/错误体提供示例与描述，确保合同测试稳定。

### 示例路由建议

- `POST /v1/agents/{agent_id}/query`
  - 入参：`tenant_id`、`input`、可选 `tools`/`params`；
  - 行为：转发至 `schedule_agent`（智能调度），记录 `intermediate_steps` 并返回 `AgentResponse`。
- `POST /v1/docs/upload`
  - 入参：文件流与元数据；
  - 行为：校验类型/大小/病毒扫描，返回 `doc_id` 与入库状态。
- `POST /v1/docs/index`
  - 行为：触发切分/嵌入/写入 FAISS（幂等，支持 `Idempotency-Key`）。
- `GET /v1/docs/{doc_id}`
  - 行为：查询文档元数据与版本信息。
- `GET /v1/health`
  - 行为：依赖探活，返回 `200` 表示可用。
- `GET /v1/metrics`
  - 行为：暴露核心指标（建议 Prometheus 格式）。

## 代码归属与目录放置（强制建议）

- `agentlz/app/routers/`：HTTP 路由定义（拆分为 `agents.py`、`docs.py`、`health.py` 等），在 `http_langserve.py` 统一 `include_router()`。
- `agentlz/schemas/`：请求/响应/错误模型，含分页、筛选、排序等通用 DTO。
- `agentlz/services/`：业务与领域逻辑（与 LLM 解耦），如文档版本化、审计、RBAC、索引生命周期管理。
- `agentlz/agents/`：Agent 编排与协作（`schedule_agent`、`planner_agent`、`execute_agent`）。
- `agentlz/tools/`：工具适配层（`@tool` 封装具体操作，执行后交由 `check` Agent 验证）。
- `agentlz/integrations/`：外部 API 客户端（带重试/限流/断路器）。
- `agentlz/core/`：日志/错误/重试/并发/模型工厂等通用能力。
- `agentlz/config/`：集中配置与 `.env` 加载验证。
- `agentlz/prompts/`：所有 Agent 提示词（中文），按 Agent 分类存放。

## 与 PyPA “src 布局”的取舍

- 当前仓库为应用型后端，非可发布库；维持现有分层即可。
- 如未来需要发布 SDK/客户端包，建议将发布目标迁移为 `src/<package>/` 结构，以避免测试误导与打包问题 (PyPA Guide: https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)。

## 实施与质量保障要点

- 统一使用 `black`/`ruff`/`isort`，Python 3.14 全量类型标注；
- 单元测试聚焦服务/工具/配置，集成测试覆盖 Agent 编排与 RAG 流程；
- 在 CI 中执行 lint/format/test，并设置关键模块最低覆盖率；
- 严禁硬编码密钥；通过 `.env` 注入敏感信息，示例变量见 `docs/dev.md` 与 `.env.example`。

