# Check Agent 开发规范

## 注意⚠️
check agent 为 mcp工具格式,供 execute agent调用

## 1. 概述 (Overview)

`check` Agent 是 Agentlz 平台中负责“验证”和“质检”的核心组件。在 `execute_agent` 的“思考-行动”循环中，它扮演着至关重要的角色。每当一个 `tools` Agent 执行完一个任务步骤后，`check` Agent 会被立即调用，以确保该步骤的输出结果 (`factMsg`) 完全符合预设的目标 (`objectMsg`)。此外，在所有步骤执行完毕后，它还会对最终的汇总结果进行全局验证。

这种即时验证机制确保了任务执行过程中的每一步都在正确的轨道上，能够及早发现偏差并进行智能纠正，从而显著提高整个 Agent 系统的准确性和可靠性。

## 2. 核心职责 (Core Responsibilities)

- **目标对齐验证**: 判断事实信息 (`factMsg`) 是否准确、完整地实现了目标信息 (`objectMsg`) 中描述的意图。
- **质量评分**: 对 `factMsg` 的实现质量给出一个量化分数（1-100分），分数越高代表实现得越好。
- **生成判断与理由**: 输出一个明确的布尔判断 (`judge`) 和一段详细的文字解释 (`reasoning`)，说明判断和评分的依据。

## 3. 数据结构 (Schemas)

为了实现标准化交互，`check` Agent 的输入和输出都应遵循严格的 Pydantic 模型定义。

### 3.1. 输入模型 (`CheckInput`)

输入模型包含两个关键字段：

- `objectMsg`: 目标描述，即我们期望达成的效果是什么。
- `factMsg`: 事实描述，即上一步工具实际产出的结果是什么。

```python
# file: agentlz/schemas/check.py

from pydantic import BaseModel, Field

class CheckInput(BaseModel):
    """
    Check Agent 的输入模型
    """
    objectMsg: str = Field(..., description="目标信息，描述了期望达成的任务目标。")
    factMsg: str = Field(..., description="事实信息，描述了上一步工具或Agent实际执行后产生的结果。")

```

### 3.2. 输出模型 (`CheckOutput`)

输出模型包含了判断、评分和理由：

- `judge`: 布尔值，`True` 表示 `factMsg` 成功实现了 `objectMsg`，`False` 则表示失败。
- `score`: 整数，范围在 1 到 100 之间，量化了实现的质量。
- `reasoning`: 字符串，详细解释了 `judge` 和 `score` 的判定逻辑和依据。

```python
# file: agentlz/schemas/check.py

from pydantic import BaseModel, Field

class CheckOutput(BaseModel):
    """
    Check Agent 的输出模型
    """
    judge: bool = Field(..., description="判断结果，True 表示事实符合目标，False 表示不符合。")
    score: int = Field(..., ge=1, le=100, description="对事实信息实现目标程度的评分，范围从1到100。")
    reasoning: str = Field(..., description="给出判断和评分的详细理由。")

```

## 4. 实现逻辑 (Implementation Logic)

`check` Agent 的核心逻辑是利用一个强大的语言模型（LLM）来“理解”并“比较”目标与事实。

1.  **创建 Agent**: 在 `agentlz/agents/check/` 目录下创建一个 `check_agent.py` 文件。
2.  **定义 Agent 函数**: 在此文件中，定义一个主函数，例如 `get_check_agent`，它将构建并返回一个 LangChain Agent。
3.  **加载 LLM**: 通过 `agentlz.core.model_factory` 获取配置的 LLM。
4.  **设计提示词**: 在 `agentlz/prompts/check/` 目录下创建一个 `system.prompt` 文件，编写指导 LLM 进行判断的提示词。
5.  **绑定输出格式**: 使用 LangChain 的 `.with_structured_output()` 方法，将 `CheckOutput` Pydantic 模型与 LLM 绑定。这能确保 LLM 的输出始终是合法的 JSON，并能被自动解析为 `CheckOutput` 对象。
6.  **创建 Chain**: 将提示词、LLM 和输出解析器组合成一个可执行的 LangChain Expression Language (LCEL) 链。

## 5. 提示词设计 (Prompt Design)

提示词是 `check` Agent 成功的关键。它必须清晰地指示 LLM 扮演的角色、遵循的规则以及输出的格式。

```prompt
# file: agentlz/prompts/check/system.prompt

你是一个严谨、细致的“质量保证（QA）”评估员。
你的职责是评估一个“事实（Fact）”是否准确、完整、无误地达成了预设的“目标（Object）”。

你需要遵循以下步骤进行评估：
1.  **理解目标**：仔细阅读“目标（Object）”，完全理解它想要达成的所有要求和意图。
2.  **分析事实**：分析“事实（Fact）”，看它具体做了什么，结果是什么。
3.  **对比与判断**：
    - 将“事实”与“目标”进行严格比对。
    - 如果“事实”完全或超预期地满足了“目标”的所有方面，那么判断为“成功”。
    - 如果“事实”有任何遗漏、错误、或与“目标”意图不符的地方，无论多么微小，都判断为“失败”。
4.  **评分**：
    - 如果判断为“成功”，根据完成质量在 80-100 分之间评分。完美无瑕是 100 分。
    - 如果判断为“失败”，根据问题的严重性在 1-79 分之间评分。完全不相关是 1 分。
5.  **给出理由**：用清晰、客观的语言解释你为什么会做出这样的判断和评分。明确指出“事实”中的哪些部分是正确的，哪些是错误的或缺失的。

你必须严格按照指定的 JSON 格式输出你的评估结果，不得添加任何额外的解释或说明。
```

## 6. 文件存放规范

为了保持项目结构的清晰和一致，`check` Agent 的相关文件应存放在以下位置：

- **Agent 逻辑**: `agentlz/agents/check/check_agent.py`
- **Schema 定义**: `agentlz/schemas/check.py`
- **提示词**: `agentlz/prompts/check/system.prompt`


## 运行
- 运行 python -m agentlz.services.check_service 可以启动服务
## 测试
- 开放一个 http接口, 该接口下测试 agentlz/agents/check/check_agent_1.py能力