from __future__ import annotations

from unittest.mock import patch


def test_history_assembly_uses_zip_when_input_output_missing() -> None:
    from agentlz.services.rag.rag_service import agent_chat_get_rag

    def _fake_recent(*, record_id: int, limit: int, min_session_id: int = 0):
        return [{"count": 1, "input": None, "output": None, "zip": "摘要", "zip_status": "done"}]

    with (
        patch("agentlz.services.rag.rag_service.get_recent_sessions_for_history", side_effect=_fake_recent),
        patch("agentlz.services.rag.rag_service.repo.get_record_summary", return_value={"summary_zip": "", "summary_until_session_id": 0}),
    ):
        out = agent_chat_get_rag(agent_id=1, message="", record_id=1, meta=None)
        assert "第1轮: 摘要" in str(out.get("history") or "")
        assert "human:" not in str(out.get("history") or "")


def test_history_assembly_includes_summary_and_recent() -> None:
    from agentlz.services.rag.rag_service import agent_chat_get_rag

    def _fake_recent(*, record_id: int, limit: int, min_session_id: int = 0):
        return [
            {"count": 3, "input": {"text": "in"}, "output": {"text": "out"}, "zip": "", "zip_status": "pending"}
        ]

    with (
        patch("agentlz.services.rag.rag_service.get_recent_sessions_for_history", side_effect=_fake_recent),
        patch(
            "agentlz.services.rag.rag_service.repo.get_record_summary",
            return_value={"summary_zip": "历史摘要文本", "summary_until_session_id": 2},
        ),
    ):
        out = agent_chat_get_rag(agent_id=1, message="q", record_id=1, meta=None)
        his = str(out.get("history") or "")
        assert "历史摘要文本" in his
        assert "【最近轮次】" in his
        assert "human:in" in his
