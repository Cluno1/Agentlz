# Planner Agent 文档

**位置**
- `agentlz/agents/planner/planner_agent.py`
- 系统提示：`agentlz/prompts/planner/system.prompt`

**职责**
- 生成结构化的 `WorkflowPlan`，用于后续执行阶段；包含工具链路偏好、MCP 配置与执行指示。

**架构要点**
- 使用 `ChatPromptTemplate` 组织提示：系统信息来自常量 `PLANNER_PROMPT`（从 `prompts/planner/system.prompt` 读取）。
- 仅将 `HumanMessage` 传入 `agent.invoke`；系统提示通过 `create_agent(system_prompt=PLANNER_PROMPT)` 注入，保持统一风格。
- 输出类型为结构化对象 `WorkflowPlan`（见 `agentlz/schemas/workflow.py`）。

**WorkflowPlan 关键字段**
- `execution_chain`：`list[str]`，工具调用偏好顺序，如 `mcp -> tool -> internal`。
- `mcp_config`：`list[MCPConfigItem]`，MCP 服务器启动参数（`transport`、`command`、`args`）。
- `instructions`：`str`，规划给执行器的补充指令与步骤说明（已集成）。

**运行命令**
- 生成计划：`python -m test.planner.generate_plan`
- 输出文件：`test/planner/plan_output.json`

**环境依赖**
- `.env`：`d:\PyCharm\AgentCode\Agentlz\.env`
  - 推荐使用 `CHATOPENAI_API_KEY`、`CHATOPENAI_BASE_URL` 与 `MODEL_NAME`。
  - 若需要根据关键词查询 MCP 仓储，需配置数据库（见 `docs/test/env.md`）。

**系统提示规范（节选）**
- 需同时给出：`execution_chain`、`mcp_config`、`instructions`。
- `instructions` 用于指导执行器如何按偏好顺序调用工具、处理响应与回退策略。

**示例输出（简化）**
```json
{
  "execution_chain": ["mcp", "tool", "internal"],
  "mcp_config": [
    {
      "keyword": "file",
      "transport": "stdio",
      "command": "node",
      "args": ["server.js"],
      "metadata": {"description": "file operations"}
    }
  ],
  "instructions": "先尝试通过 MCP 获取信息；若失败使用本地工具。"
}
```

**与执行器协作**
- 执行器会读取 `plan_output.json` 并优先遵循 `instructions`。
- 若无 `instructions`，则按 `execution_chain` 偏好进行工具调用规划。

**相关文档**
- 测试说明：`docs/test/tests.md`
- 环境与数据库：`.env.expamle`