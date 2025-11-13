import asyncio
import json
from typing import Any, Dict, List
from agentlz.agents.planner.planner_agent import plan_workflow_chain
from agentlz.agents.executor.executor_agnet import MCPChainExecutor
from agentlz.schemas.workflow import WorkflowPlan, MCPConfigItem

def main():
    user_input = "请根据原始数字进行两次平方和一次与原始数字的相加，输出一段200字的童话，初始输入：3"
    print("开始流程编排...")
    plan_or_text = plan_workflow_chain(user_input)
    print("编排结果：", plan_or_text)
    try:
        # 首选使用结构化 dataclass
        if isinstance(plan_or_text, WorkflowPlan):
            plan = plan_or_text
        else:
            # 兼容旧路径：字符串或字典 -> 转换为 WorkflowPlan
            raw: Any = plan_or_text
            if isinstance(raw, str):
                raw = json.loads(raw)
            if isinstance(raw, dict):
                # 获取执行链列表
                exec_chain = raw.get("execution_chain", [])
                # 获取MCP配置项列表
                mcp_items: List[Dict[str, Any]] = raw.get("mcp_config", [])
                
                # 构建WorkflowPlan对象
                plan = WorkflowPlan(
                    # 执行链
                    execution_chain=exec_chain,
                    # MCP配置，逐个转换字典项为MCPConfigItem对象
                    mcp_config=[
                        MCPConfigItem(
                            name=item.get("name", ""),
                            transport=item.get("transport", "stdio"),
                            command=item.get("command", ""),
                            args=item.get("args", []),
                        )
                        for item in mcp_items
                    ],
                )
            else:
                raise TypeError("无法识别的编排结果类型")

        print("开始执行链路...")
        
         # 创建MCP链执行器实例，传入执行计划
        executor = MCPChainExecutor(plan)
        # 将原始用户意图作为执行输入，便于代理理解任务
        input_data = user_input
        final_result = asyncio.run(executor.execute_chain(input_data))
        print("最终结果:", final_result)
    except Exception as e:
        print("解析或执行出错：", e)

if __name__ == "__main__":
    main()