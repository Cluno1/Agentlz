import asyncio
import json
from pathlib import Path

from agentlz.agents.executor.executor_agnet import MCPChainExecutor
from agentlz.schemas.workflow import WorkflowPlan, MCPConfigItem


def main():
    # 从 test/planner/plan_output.json 读取执行计划
    plan_path = Path(__file__).resolve().parent.parent / "planner" / "plan_output.json"
    if not plan_path.exists():
        raise FileNotFoundError(f"未找到计划文件: {plan_path}")
    raw = json.loads(plan_path.read_text(encoding="utf-8"))

    # 构造 WorkflowPlan（包含 instructions）
    mcp_items = [
        MCPConfigItem(
            name=item.get("name", ""),
            transport=item.get("transport", "stdio"),
            command=item.get("command", "python"),
            args=item.get("args", []),
        )
        for item in raw.get("mcp_config", [])
    ]
    plan = WorkflowPlan(
        execution_chain=raw.get("execution_chain", []),
        mcp_config=mcp_items,
        instructions=raw.get("instructions", ""),
    )

    print("开始执行链路...")
    executor = MCPChainExecutor(plan)
    input_data = "3"
    final_result = asyncio.run(executor.execute_chain(input_data))

    # 打印执行统计信息
    print("执行统计:", executor)

    print("最终结果:", final_result)


if __name__ == "__main__":
    main()