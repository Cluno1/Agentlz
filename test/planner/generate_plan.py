import os
import json
from typing import Any, Dict

from agentlz.agents.planner.planner_agent import plan_workflow_chain
from agentlz.schemas.workflow import WorkflowPlan, MCPConfigItem


def main():
    user_input = "请根据原始数字进行两次平方和一次与原始数字的相加，运用双关语言输出一段有趣的话，初始输入：3"
    print("开始流程编排...")
    plan_or_text = plan_workflow_chain(user_input)
    print("编排结果：", plan_or_text)

    # 额外：将计划保存为 JSON，便于执行器独立使用
    try:
        output_path = os.path.join(os.path.dirname(__file__), "plan_output.json")
        raw: Dict[str, Any] | None = None
        if isinstance(plan_or_text, WorkflowPlan):
            raw = {
                "execution_chain": plan_or_text.execution_chain,
                "mcp_config": [
                    {
                        "name": item.name,
                        "transport": item.transport,
                        "command": item.command,
                        "args": item.args,
                    }
                    for item in plan_or_text.mcp_config
                ],
                # 可选：保存 planner 的执行指示，供 executor 使用
                "instructions": getattr(plan_or_text, "instructions", ""),
            }
        elif isinstance(plan_or_text, str):
            raw = json.loads(plan_or_text)
        elif isinstance(plan_or_text, dict):
            raw = plan_or_text
        if raw is not None:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(raw, f, ensure_ascii=False, indent=2)
    except Exception as e:
        import sys
        print("⚠️ 计划保存失败:", repr(e), file=sys.stderr)


if __name__ == "__main__":
    main()