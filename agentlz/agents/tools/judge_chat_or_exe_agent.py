"""用于判断当前请求应走 chat 还是 exe 模式的意图识别 Agent。"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from langchain_core.prompts import ChatPromptTemplate

from agentlz.config.settings import get_settings
from agentlz.core.logger import setup_logging
from agentlz.core.model_factory import get_model
from agentlz.prompts.tools.judge_chat_or_exe_prompt import (
    INTENT_CLASSIFIER_SYSTEM_PROMPT,
)


def classify_chat_or_exe_intent(
    user_input: str,
    agent_description: Optional[str] = None,
) -> Tuple[str, float, str]:
    """
    根据用户自然语言输入与 Agent 描述信息，判断当前请求适合进入 chat 还是 exe 模式。

    参数:
        user_input: 用户本次请求的自然语言内容。
        agent_description: 当前 Agent 的描述信息（可为空，用于辅助判断）。

    返回值:
        一个三元组 (intent, confidence, reason)：
            intent: "chat" 或 "exe"，表示推荐模式。
            confidence: 0.0–1.0 的浮点数，表示置信度。
            reason: 简短中文理由，说明判定依据。
    """
    settings = get_settings()
    logger = setup_logging(
        level="DEBUG",
        name="agentlz.intent_classifier",
        prefix="[IntentClassifier]",
    )
    llm = get_model(settings)
    if llm is None:
        logger.error("Intent classifier model not configured")
        return "chat", 0.0, "model_not_configured"

    # 构建提示词模板：system 描述分类标准，human 注入用户输入与 Agent 描述
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", INTENT_CLASSIFIER_SYSTEM_PROMPT),
            (
                "human",
                "用户输入：{user_input}\n\n"
                "Agent 描述：{agent_description}\n\n"
                "请根据上述规则，只输出严格符合要求的 JSON。",
            ),
        ]
    )

    try:
        # 将输入格式化为消息序列，并调用底层模型
        messages = prompt.format_messages(
            user_input=str(user_input or ""),
            agent_description=str(agent_description or ""),
        )
        resp: Any = llm.invoke(messages)

        # 优先从 resp.content 读取文本内容，若不存在则退回 str(resp)
        content = getattr(resp, "content", None)
        if not isinstance(content, str) or not content.strip():
            content = str(resp)
        txt = str(content).strip()

        # 尝试从返回文本中截取最外层的 JSON 片段
        start = txt.find("{")
        end = txt.rfind("}")
        if start != -1 and end != -1 and end >= start:
            txt = txt[start : end + 1]

        data: Dict[str, Any] = {}
        try:
            import json

            data = json.loads(txt)
        except Exception as e:
            logger.error(f"intent classifier json parse failed: {e}")
            data = {}

        # 归一化 intent 字段，只允许 chat 或 exe
        intent = str(data.get("intent") or "").strip().lower()
        if intent not in ("chat", "exe"):
            intent = "chat"

        # 解析置信度，异常场景统一回退到 0.0
        try:
            confidence = float(data.get("confidence") or 0.0)
        except Exception:
            confidence = 0.0

        # 解析判定理由，保持为简短中文文本
        reason = str(data.get("reason") or "").strip() or "no_reason"

        return intent, confidence, reason
    except Exception as e:
        # 任意异常均回退为 chat 模式，避免影响主链路可用性
        logger.error(f"intent classification failed: {e}")
        return "chat", 0.0, "intent_classification_failed"


