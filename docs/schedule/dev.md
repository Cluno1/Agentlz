# 我已梳理入口与编排结构；现在已添加一个最小可执行的总调度 agent，并挂到 HTTP 路由。

## 新增内容

- 新增 agentlz/agents/schedule_1_agent.py
  - 读取 agent_tables/plan.py 、 check.py 、 tools.py 的可信度表；
  - 表为空时直接返回“不执行任何调用”的响应；
  - 存在 plan 时输出最小化的“步骤骨架”和工具/检查候选（暂不触发远程 MCP 调用）。
- 更新 agentlz/schemas/responses.py
  - 增加 ScheduleResponse 响应模型，统一返回字段（ status 、 selected_plan_agent_id 、 selected_tools_agent_ids 、 steps 、 check_passed 、 final_summary 、 error ）。
- 初始化可信度表占位
  - agentlz/agent_tables/plan.py 导出 PLAN_AGENTS: List[Dict[str, Any]] = []
  - agentlz/agent_tables/check.py 导出 CHECK_AGENTS: List[Dict[str, Any]] = []
  - agentlz/agent_tables/tools.py 导出 TOOLS_AGENTS: List[Dict[str, Any]] = []
  - agentlz/agent_tables/schedule.py 预留 SCHEDULE_AGENTS （本次未使用）
- 暴露 FastAPI 路由
  - 在 agentlz/app/http_langserve.py 增加 add_routes(..., path="/agents/schedule_1")
## 使用方式

- 启动 HTTP 服务（示例）
  - 安装 uvicorn 后运行： uvicorn agentlz.app.http_langserve:app --port 8000
- 调用调度 Agent
  - POST 到 http://localhost:8000/agents/schedule_1/invoke ，请求体为 {"input": "你的业务输入"} 。
  - 返回字符串摘要，包含状态、所选 plan、工具候选与步骤数等。
- 程序内调用
  - from agentlz.agents.schedule_1_agent import query; print(query("你的业务输入"))
## 可信度表格式

- 当前位置默认空表；如需启用调度，请在如下文件填入 MCP Agent 信息（越高 trust 越优先）：
- agentlz/agent_tables/plan.py
  - PLAN_AGENTS = [{"id": "planner_mcp_1", "trust": 95, "endpoint": "stdio://..."}]
- agentlz/agent_tables/check.py
  - CHECK_AGENTS = [{"id": "checker_mcp_1", "trust": 90, "endpoint": "stdio://..."}]
- agentlz/agent_tables/tools.py
  - TOOLS_AGENTS = [{"id": "tool_mcp_1", "trust": 85, "endpoint": "stdio://..."}]
## 工作逻辑

- 按文档要求：优先选用 plan 可信度最高的 MCP；输出规范（最小化骨架）：
  - 步骤 1：根据规范调用第一个工具（占位，不实际远程调用）
  - 步骤 2：调用检查 Agent 校验输出（占位）
- 空表处理：
  - plan 空 → status = "no_plan_agents" ，不执行调用
  - tools 或 check 空 → status = "missing_tools_or_checks" ，仅输出骨架
## 后续工作

- 当前实现为“最小可执行版本”，仅输出规范与骨架；未集成 MCP 客户端的真实远程调用。
- 下一步可按 endpoint 接入 MCP 客户端（例如 STDIO/HTTP），完成：
  - 调用最高可信度 plan 生成 check list/执行大纲
  - 按顺序调用 tools 并传参
  - 使用 check 校验并在不通过时依次重试同类工具
  - 汇总 LLM 输出与结构化响应