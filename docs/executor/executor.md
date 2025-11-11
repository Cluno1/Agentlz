# Executor Agent 文档

**位置**
- 代码：`agentlz/agents/executor/executor_agnet.py`
- 系统提示：`agentlz/prompts/executor/system.prompt`

**职责**
- 读取并使用由 Planner 生成的 `WorkflowPlan` 与 `instructions`，按工具链路偏好执行任务。
- 优先遵循 `instructions`；若未提供，则按 `execution_chain`（例如：`mcp -> tool -> internal`）规划工具调用。

**架构要点**
- 使用 `ChatPromptTemplate` 组织提示：系统信息来自常量 `EXECUTOR_PROMPT`（从 `prompts/executor/system.prompt` 读取）。
- 在执行前，若计划内存在 `instructions`，会追加为系统消息以指导工具调用与结果处理。
- 仅将 `HumanMessage` 传入 `agent.ainvoke`；系统提示通过 `create_agent(system_prompt=EXECUTOR_PROMPT)` 注入，保持与 `planner_agent` 一致的风格。
- 通过 `MCPChainExecutor` 按计划中的 `mcp_config` 启动 MCP 服务器并加载工具。

**输入数据（WorkflowPlan）**
- `execution_chain`：`list[str]`，工具调用偏好顺序。
- `mcp_config`：`list[MCPConfigItem]`，MCP 服务器启动参数（`transport`、`command`、`args`、`metadata`）。
- `instructions`：`str`，来自 Planner 的执行指示（若存在将被优先遵循）。

**运行命令**
- 执行固定计划：`python -m test.excutor.run_excutor`
- 计划来源：`test/planner/plan_output.json`（由 `python -m test.planner.generate_plan` 生成）

**系统提示规范（节选）**
- 当有 `instructions` 时：严格遵循其步骤与回退策略。
- 当无 `instructions` 时：根据 `execution_chain` 决定工具调用优先级；例如优先尝试 MCP，失败后使用内置工具或内部处理。

**示例计划（简化）**
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
  "instructions": "先通过 MCP 获取内容，失败则用本地工具读取。"
}
```

**环境依赖**
- `.env`：`d:\PyCharm\AgentCode\Agentlz\.env`
  - 推荐使用 `CHATOPENAI_API_KEY`、`CHATOPENAI_BASE_URL` 与 `MODEL_NAME`。
- 若执行过程需要根据关键词动态查询 MCP 仓储（通常在 Planner 阶段进行），请参考 `docs/test/env.md` 配置数据库。

**常见问题与排查**
- MCP 启动失败：检查 `mcp_config` 的 `command`/`args` 是否正确，确保依赖已安装并可执行。
- 计划文件路径错误：确认 `test/planner/plan_output.json` 已生成且路径正确。
- 数据库鉴权失败（仅当运行涉及仓储查询时）：若出现 `Access denied for user 'root'@'...'(using password: YES)`，请参考 `docs/test/env.md` 的权限配置与端口放通说明。

**相关文档**
- Planner 文档：`docs/planner.md`
- 测试说明：`docs/test/tests.md`
- 环境与数据库：`.env.expamle`