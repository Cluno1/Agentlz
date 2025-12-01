# 链路事件流 API 文档（/v1）

本文档描述责任链的流式事件接口，用于前端实时展示规划/执行/校验与最终结果。

- 路由前缀：`/v1`
- 多租户：必须在请求头携带租户标识 `X-Tenant-ID`（或 `.env` 中的 `TENANT_ID_HEADER`，默认 `X-Tenant-ID`）
- 认证：在请求头携带 `Authorization: Bearer <token>`
- 传输：`text/event-stream`（Server-Sent Events，SSE），事件按帧推送

## 1) GET /v1/chain/stream （流式事件）

- 说明：根据用户输入触发责任链，实时返回事件帧；每帧包含三行：`event:`、`id:`、`data:`，以空行结尾
- 头部：
  - `X-Tenant-ID: default`
  - `Authorization: Bearer <token>`
  - `Accept: text/event-stream`
- 查询参数：
  - `user_input`（必填）：用户输入文本

示例请求（curl）：
```
curl -N -H "X-Tenant-ID: default" \
     -H "Authorization: Bearer <token>" \
     -H "Accept: text/event-stream" \
     "http://localhost:8000/v1/chain/stream?user_input=写一个周报&max_steps=10"
```

示例事件帧：
```
event: chain.step
id: 1
data: {"evt":"chain.step","seq":1,"ts":"2025-11-27T12:34:56Z","trace_id":"<uuid>","schema":"v1","payload":"planner"}


event: planner.plan
id: 2
data: {"evt":"planner.plan","seq":2,"ts":"2025-11-27T12:34:57Z","trace_id":"<uuid>","schema":"v1","payload":{"execution_chain":["executor","check"],"mcp_config":[/*...*/],"instructions":"..."}}


event: chain.step
id: 3
data: {"evt":"chain.step","seq":3,"ts":"2025-11-27T12:34:57Z","trace_id":"<uuid>","schema":"v1","payload":"executor"}


event: call.start
id: 4
data: {"evt":"call.start","seq":4,"ts":"2025-11-27T12:34:58Z","trace_id":"<uuid>","schema":"v1","payload":{"name":"search","status":"start","input":"...","output":"","server":""}}


event: call.end
id: 5
data: {"evt":"call.end","seq":5,"ts":"2025-11-27T12:34:59Z","trace_id":"<uuid>","schema":"v1","payload":{"name":"search","status":"success","input":"...","output":"...","server":"executor"}}


event: chain.step
id: 6
data: {"evt":"chain.step","seq":6,"ts":"2025-11-27T12:35:00Z","trace_id":"<uuid>","schema":"v1","payload":"check"}


event: check.summary
id: 7
data: {"evt":"check.summary","seq":7,"ts":"2025-11-27T12:35:01Z","trace_id":"<uuid>","schema":"v1","payload":{"judge":true,"score":90,"reasoning":"...","tool_assessments":[/*...*/]}}


event: final
id: 8
data: {"evt":"final","seq":8,"ts":"2025-11-27T12:35:02Z","trace_id":"<uuid>","schema":"v1","payload":"最终结果文本"}
```

### 事件类型与负载
- `chain.step`：阶段名（`planner/executor/check`），负载为字符串；来自各步骤显式发送（`agentlz/services/chain/steps/step1_planner.py:32`、`agentlz/services/chain/steps/step2_executor.py:33`、`agentlz/services/chain/steps/step3_check.py:33`）
- `planner.plan`：结构化计划 `WorkflowPlan`；来源 `ctx.plan`（`agentlz/services/chain/steps/step1_planner.py:34-36`）
- `call.start`：结构化工具调用开始 `ToolCall`；来源执行器工具回调（`agentlz/services/chain/steps/step2_executor.py:142-153`）
- `call.end`：结构化工具调用结束 `ToolCall`；来源执行器工具回调（`agentlz/services/chain/steps/step2_executor.py:157-167`），状态统一为 `success`
- `check.summary`：校验汇总 `CheckOutput`；来源 `ctx.check_result`（`agentlz/services/chain/steps/step3_check.py:37-39`）
- `final`：最终结果文本；来源 `ctx.fact_msg`。当执行未产生有效结果或达到最大步数上限时，后端会返回友好提示文本（不再发送单独的 `chain.limit` 事件）。

### 前端消费示例
```
const es = new EventSource('/v1/chain/stream?user_input=你的输入');

es.addEventListener('chain.step', e => {
  const env = JSON.parse(e.data);
  setActiveStep(env.payload);
});

es.addEventListener('planner.plan', e => {
  const env = JSON.parse(e.data);
  renderPlan(env.payload);
});

es.addEventListener('call.end', e => {
  const env = JSON.parse(e.data);
  appendToolCard(env.payload);
});

es.addEventListener('call.start', e => {
  const env = JSON.parse(e.data);
  appendToolCard(env.payload);
});

es.addEventListener('check.summary', e => {
  const env = JSON.parse(e.data);
  renderCheck(env.payload);
});

es.addEventListener('final', e => {
  const env = JSON.parse(e.data);
  setResult(env.payload);
  es.close();
});
```

### 设计说明
- 路由：`agentlz/app/routers/chain.py:10-15`（SSE）
- 生成器：`agentlz/services/chain/chain_service.py`，按 `handle → next` 推进并逐帧输出，最终统一推送 `final` 文本并结束
- 帧构造：`agentlz/services/chain/chain_service.py:127-155`（`EventEnvelope` JSON + `event/id/data` 文本帧）
- 事件壳：`agentlz/schemas/events.py:4-10`
- 工作流模型：`agentlz/schemas/workflow.py:16-22,24-35`

### 约束
- 该接口为流式输出，连接在流结束前不关闭；前端在收到每帧后即可渲染，无需等待整条输出完成。
- 已包含工具调用开始事件 `call.start` 与结束事件 `call.end`；如需异常即时上报，可扩展 `error` 事件。

### 上限与提示
- 查询参数 `max_steps`（可选，默认 6）：用于控制执行步数上限；后端会与环境变量 `CHAIN_HARD_LIMIT` 取最小值。
- 当请求的 `max_steps` 超过 `CHAIN_HARD_LIMIT` 时，后端不进入执行流程，只返回一帧 `final` 提示并结束连接。
- 执行过程中达到上限时：
  - 若已有有效结果则正常返回；
  - 若无有效结果，则在 `final` 文本中返回“已达到最大步数限制（N）…”的友好提示。
  - 不再发送单独的 `chain.limit` 事件（提示统一体现在 `final` 文本）。
