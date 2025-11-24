# Chain 责任链测试

## 目的
- 从入口执行器运行完整链路（Root → Planner → Executor → Check），观察步骤轨迹与输出。
- 验证在规划失败或执行失败时的错误记录与跳转逻辑（未通过时回到 Planner）。

## 运行
```bash
python test/chain/run_chain.py
```

## 期望现象
- 控制台打印：输入、步骤轨迹、`plan/fact_msg/check_result`、错误列表（如有）。
- 步骤轨迹格式示例：
```
01. root -> passed
02. planner -> passed
03. executor -> passed
04. check -> passed
```

## 说明
- `max_steps` 默认 6，用于保护链路不至于无限循环。
- 若规划失败：会记录 `planner_failed`，执行/校验可能透传或失败，根据节点实现决定下一跳。
- 若校验未通过：会清理 `ctx.plan` 并返回到 Planner 进行重规划，直到通过或达到步数上限。