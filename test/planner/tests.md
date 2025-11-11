# Planner 测试说明

**目录**：`test/planner`

**目标**
- 仅进行流程编排，生成结构化计划 `WorkflowPlan` 并保存到 `test/planner/plan_output.json`。
- 计划包含 `execution_chain`、`mcp_config`、`instructions`，供执行器读取。

**运行命令**
- 在项目根目录：
  - `python -m test.planner.generate_plan`
- 环境配置 (.env)：详见 `.env.expamle`

```env
# 统一 .env 配置（不改 settings.py 的前提下）

# 使用 OpenAI 官方端点（二选一场景：如仅用官方）
# OPENAI_API_KEY="sk-xxxxxxxx"

# 使用 OpenAI 兼容接口（DeepSeek 等）——推荐
CHATOPENAI_API_KEY="sk-。。。"
CHATOPENAI_BASE_URL="https://api.deepseek.com/v1"

# 模型与日志
MODEL_NAME="deepseek-chat"
LOG_LEVEL="INFO"

# MySQL 连接配置（用于 MCP 仓储查询）
DB_HOST="。。。"
DB_PORT="13306"
DB_USER="root"
DB_PASSWORD="。。。"
# 注意：仓库 SQL 使用的是 agentlz 数据库
DB_NAME="agentlz"
```

**输出**
- 文件：`test/planner/plan_output.json`
- 字段：
  - `execution_chain`: 工具链路偏好顺序（例如：`math_agent_top` → `language_agent_top`）
  - `mcp_config`: MCP 服务器启动参数（`transport`、`command`、`args`、`metadata`）
  - `instructions`: 对执行器的步骤与回退策略指示

**示例（来自终端日志，节选）**
- 关键词查询与编排结果：
```
开始流程编排...
🔍 按关键词查询 MCP 结果: [... math_agent_* 列表 ...]
🔍 按关键词查询 MCP 结果: [... language_agent_* 列表 ...]
编排结果： WorkflowPlan(
  execution_chain=['math_agent_top', 'language_agent_top'],
  mcp_config=[
    MCPConfigItem(name='math_agent_top', transport='stdio', command='python', args=['d:/PyCharm/AgentCode/Agentlz/test/planner/test_tool/math_agent.py']),
    MCPConfigItem(name='language_agent_top', transport='stdio', command='python', args=['d:/PyCharm/AgentCode/Agentlz/test/planner/test_tool/language_agent.py'])
  ],
  instructions='1. 首先调用 math_agent_top 工具，输入原始数字 3...\n2. 然后将计算结果 84 传递给 language_agent_top 工具...\n3. 确保两个步骤之间的数据传递顺畅...'
)
```

**计划 JSON 示例（简化）**
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
  "instructions": "先调用 math_agent_top 对 3 进行两次平方并加回原始值得到 84；再将 84 传给 language_agent_top 生成有趣描述。"
}
```

**常见问题**
- 未生成 `plan_output.json`：确认在仓库根目录执行命令。
- 模型/API 未配置：在 `.env` 设置 `CHATOPENAI_API_KEY`、`CHATOPENAI_BASE_URL`、`MODEL_NAME`。
- 数据库鉴权失败：若涉及关键词查询（MCP 仓储），参考 `docs/test/env.md` 调整权限与端口。

**关联文件**
- Planner Agent：`agentlz/agents/planner/planner_agent.py`
- Planner Prompt：`agentlz/prompts/planner/system.prompt`