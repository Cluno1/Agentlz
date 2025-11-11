# Planner_Executor 一体化测试说明

**目录**：`test/planner_excutor`

**目标**
- 一体化流程：先通过 `planner_agent` 生成 `WorkflowPlan`（含 `execution_chain`/`mcp_config`/`instructions`），再由 `executor` 按偏好与指令执行。

**运行命令**
- 在项目根目录：
  - `python -m test.planner_executor.planner_executor`

**环境配置 (.env)**
- 详见 `docs/env.md`

```env
# 统一 .env 配置（不改 settings.py 的前提下）

# 使用 OpenAI 官方端点（二选一场景：如仅用官方）
# OPENAI_API_KEY="sk-xxxxxxxx"

# 使用 OpenAI 兼容接口（DeepSeek 等）——推荐
CHATOPENAI_API_KEY="sk-190a71f802514ea7bcc536df94e8292d"
CHATOPENAI_BASE_URL="https://api.deepseek.com/v1"

# 模型与日志
MODEL_NAME="deepseek-chat"
LOG_LEVEL="INFO"

# MySQL 连接配置（用于 MCP 仓储查询）
DB_HOST="117.72.162.89"
DB_PORT="13306"
DB_USER="root"
# 将下面密码替换为你的本地 MySQL 密码；若无密码请创建或放通
DB_PASSWORD="agentdb123456"
# 注意：仓库 SQL 使用的是 agentlz 数据库
DB_NAME="agentlz"
```

**流程示例（节选自终端日志）**
- 编排与执行摘要：
```
开始流程编排...
🔍 按关键词查询 MCP 结果: [... math_agent_* 列表 ...]
🔍 按关键词查询 MCP 结果: [... language_agent_* 列表 ...]
编排结果： WorkflowPlan(
  execution_chain=['math_agent_top', 'language_agent_top'],
  mcp_config=[...],
  instructions='1. 首先调用 math_agent_top ... 2. 然后将计算结果 84 传递给 language_agent_top ...'
)

开始执行链路...
最终结果: 根据您的初始输入数字3，我完成了以下计算和描述：
- 第一次平方：3² = 9
- 第二次平方：9² = 81
- 与原始数字相加：81 + 3 = 84
...（基于 84 与 3 的关系生成的趣味文本，略）
```

**执行逻辑**
- 优先遵循 `instructions`：作为系统消息注入，指导工具调用顺序与回退策略。
- 无 `instructions` 时：按 `execution_chain` 偏好（如：先 MCP，再工具，最后内部处理）。
- 按 `mcp_config` 启动并加载 MCP 工具，进行链式调用与结果传递。

**常见问题**
- 模型/API 未配置：在 `.env` 设置 `CHATOPENAI_API_KEY`、`CHATOPENAI_BASE_URL`、`MODEL_NAME`。
- 数据库鉴权失败：若涉及关键词查询（MCP 仓储），参考权限与端口放通设置。
- 依赖与可执行：确保 `mcp_config` 中的 `command`/`args` 可在本机执行（如需 Node/Python 脚本）。

**关联文件**
- 一体化脚本：`test/planner_excutor/planner_excutor.py`
- Planner Agent：`agentlz/agents/planner/planner_agent.py`
- Executor Agent：`agentlz/agents/executor/executor_agnet.py`
- Planner/Executor 提示词：`agentlz/prompts/planner/system.prompt`、`agentlz/prompts/executor/system.prompt`