from __future__ import annotations

from unittest.mock import patch


def test_history_assembly_uses_zip_when_input_output_missing() -> None:
    from agentlz.services.rag.rag_service import agent_chat_get_rag

    def _fake_check_session_for_rag(*, record_id: int, limit_input: int, limit_output: int):
        return [{"input": None, "output": None, "zip": "摘要"}]

    with patch("agentlz.services.rag.rag_service.check_session_for_rag", side_effect=_fake_check_session_for_rag):
        out = agent_chat_get_rag(agent_id=1, message="", record_id=1, meta=None)
        assert "zip:摘要" in str(out.get("history") or "")
        assert "human:" not in str(out.get("history") or "")

