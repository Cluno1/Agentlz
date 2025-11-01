# Agentlz

- a multi agent creation system

## 环境搭建

```bash
 创建环境：python3 -m venv .venv

 激活环境（Linux/Mac）：source .venv/bin/activate
 激活环境（Windows）：.\.venv\Scripts\activate

 安装依赖：pip install -r requirements.txt

 设置.env 环境变量

 启动:  python -m agentlz.app.cli  "what is the weather in beijing"
```

```bash
固定版本 Pip freeze > requirements.txt
```

## 简单 Agent Demo（企业级文件架构）

项目结构：

```md

agentlz/
  app/cli.py            # CLI 入口
  agents/simple_agent.py # Agent 构建与调用
  tools/weather.py       # 示例工具（天气）
  core/logger.py         # 日志封装
  core/model_factory.py  # 模型工厂
  config/settings.py     # 配置（.env 支持）
tests/
  test_settings.py
  test_tools.py
.env.example             # 环境变量示例
```

使用步骤：

1. 复制环境变量模板并填写 `OPENAI_API_KEY`

```bash
cp .env.example .env
# 或手动创建 .env 并设置 OPENAI_API_KEY
```

2.运行 CLI 示例

```bash
python -m agentlz.app.cli "what is the weather in sf"
```

说明：

- 该 Demo 使用 LangChain 最新 API 形式创建 Agent，并通过 `@tool` 暴露基础工具。
- 配置集中管理，便于在企业环境中扩展模型、日志、鉴权等。

## 开发规范

**整体思路**

- 采用分层与模块化的目录结构，隔离入口、编排、工具、基础设施、配置与观测。
- 依赖方向自顶向下（入口 → 编排 → 工具/服务 → 基础设施），避免横向耦合与循环依赖。

**目录结构**

- `agentlz/app/`：应用入口层（CLI、HTTP 服务、批处理脚本）。
- `agentlz/agents/`：Agent 编排层（不同场景的 Agent 构建与协作）。
- `agentlz/tools/`：工具封装层（`@tool` 工具与适配器）。
- `agentlz/workflows/` 或 `agentlz/graphs/`：流程编排/有向图（LangGraph 状态与节点）。
- `agentlz/memory/`：记忆与存储（会话记忆、向量库、检查点）。
- `agentlz/prompts/`：提示词与模板（系统提示、格式指令、少样本示例）。
- `agentlz/schemas/`：数据与响应结构（`pydantic`/`dataclass` 模型）。
- `agentlz/services/`：业务服务层（领域逻辑，尽量不直接依赖 LLM）。
- `agentlz/integrations/`：外部系统集成（三方 API 客户端封装）。
- `agentlz/core/`：基础设施与通用能力（日志、错误、重试、并发、模型工厂）。
- `agentlz/config/`：配置管理（统一读取 `.env`，集中验证与默认值）。
- `tests/`：测试（单元与集成，按包名对齐）。
- `scripts/`：开发运维脚本（lint、test、format、publish）。
- `docs/`：文档（架构说明、接口约定、运行与运维指南）。
- `deploy/`：交付与部署（CI、Docker、K8s/Helm 模板）。
- `examples/`：示例（最小可运行示例与沙盒数据）。
- `.env.example`：环境变量样例（不提交真实密钥）。

**各包应该放什么代码**

- `agentlz/app/`
- `cli.py`：命令行入口，通过 `typer` 暴露命令如 `query`。
- `http_server.py`：HTTP API 入口（如 `FastAPI`），对外暴露 `/query` 等接口。
- `startup.py`：应用级初始化（日志级别、健康检查、全局中间件）。
- `agentlz/agents/`
- `simple_agent.py`：使用 `create_agent` 创建基础 Agent；绑定工具与系统提示。
- `planner_agent.py`：分解任务的规划 Agent，结合步骤提示或思维链。
- `multi_agent_orchestrator.py`：多 Agent 协作调度与消息路由。
- `agentlz/tools/`
- `weather.py`：`@tool` 示例，演示工具定义与参数校验。
- `search.py`：搜索工具，封装具体搜索客户端并处理结果清洗。
- `rag_retriever.py`：检索增强工具，封装切分器、嵌入与向量库查询。
- `agentlz/workflows/` / `agentlz/graphs/`
- `support_ticket_graph.py`：基于 LangGraph 的状态机/图式编排，定义节点、边与中断恢复。
- `planning_executor_graph.py`：Plan-and-Execute 流程，集成规划、执行与观测。
- `agentlz/memory/`
- `checkpoint.py`：对话检查点存储（内存/外部存储）。
- `vectorstore.py`：与 Chroma/Milvus/Pinecone 的向量存储适配器。
- `memory_router.py`：短期/长期记忆路由策略。
- `agentlz/prompts/`
- `system_prompt.txt`：系统提示词文本，便于审阅与版本化。
- `templates.py`：集中管理提示模板与格式说明（如 JSON 输出指令）。
- `agentlz/schemas/`
- `responses.py`：响应结构（`pydantic` 模型），如 `AgentResponse`、`WeatherResponse`。
- `events.py`：工具事件、工作流事件模型。
- `types.py`：通用类型别名与枚举。
- `agentlz/services/`
- `order_service.py`：订单相关的纯业务逻辑（无模型调用）。
- `travel_plan_service.py`：旅行计划逻辑（拆分、合并、校验）。
- `agentlz/integrations/`
- `openai_client.py`：LLM 客户端初始化与重试、超时策略。
- `search_client.py`：搜索引擎封装（DuckDuckGo、Bing 等）。
- `crm_client.py`：企业内部系统 API 封装。
- `agentlz/core/`
- `logger.py`：统一日志入口与格式。
- `errors.py`：自定义异常体系与错误码。
- `retry.py`：通用重试与熔断策略。
- `concurrency.py`：并发工具（队列、线程池/异步工具）。
- `model_factory.py`：模型工厂（基于配置生成聊天模型与参数）。
- `agentlz/config/`
- `settings.py`：集中读取 `.env`，提供 `Settings` 对象（模型参数、日志级别、开关）。
- `feature_flags.py`：特性开关管理（灰度、A/B 测试）。
- `tests/`
- `test_settings.py`：配置加载与默认值验证。
- `test_tools.py`：工具的入参/出参与错误路径测试。
- `test_agents.py`：Agent 编排与工具调用的集成测试（使用假客户端或本地 stub）。
- `test_workflows.py`：图式流程的节点与状态迁移测试。

**分层与依赖约束**

- 入口层（`app`）依赖编排层（`agents`），不可反向依赖。
- 编排层依赖工具/服务/基础设施层（`tools`、`services`、`core`、`config`）。
- 工具层与服务层可依赖 `integrations` 与 `core`，不可依赖 `app` 或上层 `agents`。
- `prompts`、`schemas` 为横切关注点，仅提供数据与模板，不引入业务耦合。
- 严禁循环依赖；保持模块边界清晰、单向。

**配置与敏感信息**

- 使用 `.env` 与 `agentlz/config/settings.py` 管理变量，如 `OPENAI_API_KEY`、`MODEL_NAME`、`LOG_LEVEL`。
- 在 `model_factory.py` 读取配置生成模型实例，避免在业务代码中直接硬编码。
- 通过 `feature_flags.py` 控制新功能灰度与开关，提升可观测与回滚能力。

**测试与质量保障**

- 单元测试聚焦纯逻辑（工具、服务、配置）；集成测试覆盖 Agent 与流程编排。
- 为外部集成提供 stub/mock，避免测试依赖外部网络。
- 引入静态检查与格式化（如 `ruff`/`flake8`、`black`），在 CI 中执行。
- 建议在 `scripts/` 提供一键运行脚本：`lint.ps1`、`test.ps1`、`format.ps1`。

**运行与部署**

- CLI：`python -m agentlz.app.cli query "..."` 提供本地快速验证入口。
- HTTP：在 `app/http_server.py` 暴露 REST/WS 接口，便于对外服务。
- 包装与发布：使用 `pyproject.toml` 定义包信息与入口点，便于内部发布与版本管理。
- 部署：`deploy/` 下放置 Docker/K8s/Helm 清单，结合环境变量与密钥管理。

**命名与组织建议**

- 文件命名清晰反映职责：`*_agent.py`、`*_tool.py`、`*_graph.py`、`*_service.py`。
- 提示词与响应结构统一在 `prompts/`、`schemas/` 管理，方便审阅与复用。
- 日志、错误、重试等横切关注点统一放在 `core/`，避免散落在业务代码中。
- 通过 `integrations/` 隔离第三方依赖，便于替换与容错。
