from pathlib import Path

# 基础系统提示词常量，供各 Agent 引用
PLANNER_PROMPT = Path(__file__).parent.joinpath("planner/system.prompt").read_text(encoding="utf-8")
EXECUTOR_PROMPT = Path(__file__).parent.joinpath("executor/system.prompt").read_text(encoding="utf-8")