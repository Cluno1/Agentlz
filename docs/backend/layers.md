# 后端分层与依赖约束

本文档聚焦企业后端的架构分层与依赖约束，确保系统可维护、可扩展与可审计。整体思想与约束与 `../dev.md` 保持一致，并结合当前仓库的实际目录进行落地说明。

## 设计目标
- 清晰的职责边界：入口、编排、业务、数据访问、基础设施分离
- 单向依赖与可替换：层与层之间保持单向、低耦合，可独立演进
- 多租户与安全：所有接口与数据访问遵循租户隔离、鉴权与审计
- 可测试与可观测：分层天然适配单元/集成测试与日志/指标/追踪

## 分层总览
- `app/`：应用入口层（HTTP/CLI/批处理）。暴露 `/v1/*` 接口或命令行入口。
- `agents/`：编排层（不同场景的 Agent 构建与协作，含 MCP 交互）。
- `services/`：业务服务层（领域逻辑封装，避免直接依赖 LLM 与持久化）。
- `repositories/`：数据访问层（MySQL/FAISS 等持久化封装，不含业务逻辑）。
- `tools/`：工具封装层（LangChain `@tool`、三方适配器/桥接）。
- `integrations/`：外部系统客户端（第三方 API 的可靠封装，带重试/限流）。
- `core/`：基础设施与通用能力（日志、错误、重试、并发、模型工厂）。
- `schemas/`：数据与响应结构（`pydantic`/`dataclass`，无业务代码）。
- `prompts/`：提示词与模板（系统提示、少样本示例，统一存放中文）。
- `config/`：配置管理（集中读取 `.env`，统一校验与默认值）。

> 说明：上述分层与当前仓库的目录一一对应（见下文“目录结构对照”），新增模块需严格遵循边界约束。

## 层职责与边界
- `app` 层
  - 职责：对外暴露接口/命令；将请求参数校验后交给下层处理；返回统一响应结构。
  - 依赖：可依赖 `agents`/`services`/`schemas`/`config`/`core`；不可反向被依赖；不可直接访问数据库。
- `agents` 层
  - 职责：编排工作流（如计划生成、工具调用、验证循环）；与 MCP 协议交互。
  - 依赖：可依赖 `tools`/`services`/`schemas`/`core`/`config`；不可依赖 `app`。
- `services` 层
  - 职责：纯业务逻辑封装；聚合调用 `repositories` 与 `integrations`；实现租户与权限校验。
  - 依赖：可依赖 `repositories`/`integrations`/`core`/`schemas`/`config`；不可依赖 `agents`/`app`。
- `repositories` 层
  - 职责：数据持久化访问（MySQL/FAISS）；提供原子化、可复用的数据操作。
  - 依赖：可依赖 `core`/`config`/第三方库；不包含业务分支；不可依赖 `services`。
- `tools` 层
  - 职责：工具封装与适配（LangChain 工具、Markdown 渲染、检索等）。
  - 依赖：可依赖 `services`/`integrations`/`core`；不可依赖 `app`/`agents`。
- `integrations` 层
  - 职责：外部 API 客户端，统一重试、限流与断路器；保持纯粹的 I/O 职责。
  - 依赖：可依赖 `core`/`config`；不可依赖上层业务。
- `core` 层
  - 职责：横切基础设施（日志、错误、重试、并发与模型工厂）；不承载业务。
  - 依赖：尽量零外部依赖；为所有上层提供统一能力。
- `schemas` 层
  - 职责：统一数据结构（请求/响应/实体）；无数据库访问与业务逻辑。
  - 依赖：仅依赖标准库与 `pydantic`；被所有上层读取。
- `prompts` 层
  - 职责：提示词与模板；中文维护；与 `agents` 协作。
  - 依赖：无代码依赖（文本资源）；被 `agents`/`tools` 使用。
- `config` 层
  - 职责：集中配置读取与校验（`settings.py`）；敏感信息不硬编码。
  - 依赖：可依赖 `pydantic_settings` 等；被所有层读取。

## 依赖约束（必须遵守）
- `app → agents/services/schemas/config/core`，禁止反向依赖
- `agents → tools/services/schemas/core/config`，禁止依赖 `app`
- `services → repositories/integrations/core/schemas/config`，禁止依赖 `agents/app`
- `repositories → core/config`，禁止依赖 `services/agents/app`
- `tools → services/integrations/core`，禁止依赖 `app/agents`
- `integrations → core/config`，禁止依赖上层
- `schemas/prompt` 仅被动依赖；不依赖业务或 I/O
- `core` 不依赖上层；作为横切能力向上提供

## 目录结构对照（当前仓库）
与 `../dev.md` 的“目录结构”一致，当前项目主要目录如下（仅列出关键后端相关）：

- `agentlz/app/`：HTTP/CLI 入口（如 `http_langserve.py`、`cli.py`）
- `agentlz/agents/`：编排层（Planner/Multi/Markdown 等）
- `agentlz/services/`：业务服务层
- `agentlz/repositories/`：数据访问层（MySQL/FAISS）
- `agentlz/tools/`：工具封装层
- `agentlz/integrations/`：外部系统集成
- `agentlz/core/`：基础设施（`logger.py`、`model_factory.py` 等）
- `agentlz/schemas/`：数据与响应结构（如 `responses.py`）
- `agentlz/prompts/`：提示词与模板
- `agentlz/config/`：配置（`settings.py`）
- `docs/backend/`：后端开发文档（本目录）

新增模块时请保持与上述目录一致，避免跨层耦合。

## 接口约定与多租户（摘要）
- 路由前缀：`/v1`；统一使用 `schemas/responses.py` 定义响应结构
- 鉴权与 RBAC：建议使用 `JWT`；接口必须校验租户与权限
- 多租户：通过 `TENANT_ID_HEADER`（默认 `X-Tenant-ID`）或 Token 声明
- 输入校验：使用 `pydantic` 模型；分页/排序/搜索入参统一校验与白名单
- 审计与速率：记录敏感操作审计；对公共接口配置 QPS/QPM 限流

完整细节、术语与实施说明请参见 `../dev.md` 的“安全与合规”“API 设计规范”“日志与可观测”等章节。

## 测试与质量保障（摘要）
- 单元测试：`core`、`services` 与 `repositories` 的纯逻辑优先
- 集成测试：覆盖关键编排与数据访问；使用本地 MySQL/FAISS
- CI 质量门槛：`ruff`、`black`、`pytest`；关键模块设置覆盖率目标

## 实施要求
- 所有新增代码必须放置在对应分层目录；禁止跨层直接访问
- 不在业务层抛裸异常；统一在 `core/errors.py` 映射为 HTTP 状态码
- 配置统一在 `config/settings.py` 中加载；敏感信息通过 `.env` 注入
- 提示词统一在 `prompts/` 目录下，并使用中文编写与维护

——

版本：初稿（用于落地分层与约束）；后续将补充 API、编码规范与运维文档。