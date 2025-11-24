import asyncio
from typing import Any

from agentlz.services.chain.chain_service import run_chain


def pretty_steps(steps: list[dict[str, Any]]) -> str:
    rows = []
    for i, s in enumerate(steps, 1):
        name = s.get("name")
        status = s.get("status")
        rows.append(f"{i:02d}. {name} -> {status}")
    return "\n".join(rows)


def main():
    user_input = "请根据原始数字进行两次平方和一次与原始数字的相加，运用双关语言输出一段有趣的话，初始输入：3"
    ctx = asyncio.run(run_chain(user_input, max_steps=6))
    print("输入:", user_input)
    print("步骤轨迹:\n" + pretty_steps(ctx.steps))
    for i, s in enumerate(ctx.steps, 1):
        if s.get("name") == "check":
            print(f"Check步骤#{i} 输出: {s.get('output')}")
    print("规划(plan):", ctx.plan)
    print("执行输出(fact_msg):", ctx.fact_msg)
    print("校验(check_result):", ctx.check_result)
    if ctx.errors:
        print("错误列表:", ctx.errors)


if __name__ == "__main__":
    main()