from __future__ import annotations

import json
from typing import Any, Dict, Optional
from unittest.mock import patch


def test_get_sessions_by_record_paginated_ignores_request_id_in_meta() -> None:
    from agentlz.services.rag import rag_service

    record_row = {"id": 65, "agent_id": 13, "meta": {"user_id": "131144", "request_id": "r1"}}

    with (
        patch("agentlz.services.rag.rag_service.repo.get_record_by_id", return_value=record_row),
        patch(
            "agentlz.services.rag.rag_service.sess_repo.list_sessions_by_record_paginated",
            return_value=([], 0),
        ),
    ):
        out = rag_service.get_sessions_by_record_paginated(
            agent_id=13,
            meta={"user_id": "131144"},
            record_id=65,
            page=1,
            per_page=10,
        )
        assert out == {"rows": [], "total": 0}


def test_agent_chat_service_does_not_persist_request_id_into_record_meta() -> None:
    from agentlz.services import agent_service

    captured: Dict[str, Any] = {}

    def _fake_rag(*, agent_id: int, message: str, record_id: int, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        captured["meta"] = meta
        return {"record_id": 1, "message": message, "doc": "", "history": ""}

    def _fake_stream(*, agent_id: int, record_id: int, out: Dict[str, Any], meta: Optional[Dict[str, Any]] = None):
        yield f"data: {json.dumps({'record_id': int(record_id)})}\n\n"
        yield "data: ok\n\n"
        yield "data: [DONE]\n\n"

    with (
        patch("agentlz.services.agent_service.agent_chat_get_rag", side_effect=_fake_rag),
        patch("agentlz.services.agent_service.agent_llm_answer_stream", side_effect=_fake_stream),
        patch("agentlz.services.agent_service.acquire_chat_lock", return_value=True),
        patch("agentlz.services.agent_service.release_chat_lock", return_value=True),
        patch("agentlz.services.agent_service.sess_repo.get_session_by_request_id", return_value=None),
    ):
        gen = agent_service.agent_chat_service(
            agent_id=13,
            message="hi",
            record_id=-1,
            meta={"user_id": "131144"},
        )
        list(gen)

    meta_for_record = captured.get("meta")
    assert isinstance(meta_for_record, dict)
    assert meta_for_record.get("user_id") == "131144"
    assert "request_id" not in meta_for_record

