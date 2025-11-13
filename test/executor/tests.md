# Executor 测试说明

**目录**：`test/executor`

**目标**
- 读取并执行 `test/planner/plan_output.json` 的 `WorkflowPlan`。
- 优先遵循计划中的 `instructions`，否则按 `execution_chain` 进行工具调用（如：`math_agent_top` → `language_agent_top`）。

**运行命令**
- 在项目根目录：
  - `python -m test.executor.run_executor  
- 环境配置 (.env)：`.env.expamle`

```env
# 统一 .env 配置（不改 settings.py 的前提下）

# 使用 OpenAI 官方端点（二选一场景：如仅用官方）
# OPENAI_API_KEY="sk-xxxxxxxx"

# 使用 OpenAI 兼容接口（DeepSeek 等）——推荐
CHATOPENAI_API_KEY="。。。"
CHATOPENAI_BASE_URL="https://api.deepseek.com/v1"

# 模型与日志
MODEL_NAME="deepseek-chat"
LOG_LEVEL="INFO"

# MySQL 连接配置（用于 MCP 仓储查询）
DB_HOST="117.72.162.89"
DB_PORT="13306"
DB_USER="root"
DB_PASSWORD="agentdb123456"
# 注意：仓库 SQL 使用的是 agentlz 数据库
DB_NAME="agentlz"
```
- 需先生成计划：`python -m test.planner.generate_plan`

**执行示例（来自终端日志，节选）**
```
开始执行链路...
最终结果: 根据您的初始输入数字3，我完成了以下计算和描述：

**计算过程：**
- 第一次平方：3² = 9
- 第二次平方：(3²)² = 9² = 81
- 与原始数字相加：81 + 3 = 84

**有趣的双关描述：**
...（基于 84 与 3 的关系生成的趣味文本，略）
```

**执行逻辑**
- 若存在 `instructions`：将其作为系统消息注入，指导工具调用顺序与回退策略。
- 若不存在 `instructions`：根据 `execution_chain` 决定优先尝试的工具（优先 MCP），失败后使用其它工具或内部处理。
- 启动与加载 MCP：根据计划中的 `mcp_config`（`transport`、`command`、`args`）启动相应服务并加载工具。

**计划 JSON 示例（与 Planner 输出配套，简化）**
```json
{
  "execution_chain": ["math_agent_top", "language_agent_top"],
  "mcp_config": [
    {
      "keyword": "math_agent_top",
      "transport": "stdio",
      "command": "python",
      "args": ["d:/PyCharm/AgentCode/Agentlz/test/planner/test_tool/math_agent.py"],
      "metadata": {"description": "数学计算 agent（最高可信度）"}
    },
    {
      "keyword": "language_agent_top",
      "transport": "stdio",
      "command": "python",
      "args": ["d:/PyCharm/AgentCode/Agentlz/test/planner/test_tool/language_agent.py"],
      "metadata": {"description": "语言处理 agent（最高可信度）"}
    }
  ],
  "instructions": "先通过 math_agent_top 计算得到 84，再传给 language_agent_top 生成描述。"
}
```

**常见问题**
- 找不到计划文件：确保已运行 `test/planner/generate_plan.py`。
- MCP 启动失败：检查 `command`/`args` 是否可执行，依赖是否安装。
- 模型/API 未配置：在 `.env` 设置 `CHATOPENAI_API_KEY`、`CHATOPENAI_BASE_URL`、`MODEL_NAME`。

**关联文件**
- Executor Agent：`agentlz/agents/executor/executor_agnet.py`
- Executor Prompt：`agentlz/prompts/executor/system.prompt`
- 计划来源：`test/planner/plan_output.json`