from __future__ import annotations

import json
from typing import Any, Dict, List
from unittest.mock import patch


class FakeRedis:
    def __init__(self):
        self.kv: Dict[str, str] = {}

    def ping(self) -> bool:
        return True

    def get(self, key: str) -> str | None:
        return self.kv.get(key)

    def set(self, key: str, value: str, nx: bool = False, px: int | None = None, ex: int | None = None) -> bool:
        if nx and key in self.kv:
            return False
        self.kv[key] = str(value)
        return True

    def delete(self, key: str) -> int:
        existed = 1 if key in self.kv else 0
        self.kv.pop(key, None)
        return existed

    def eval(self, script: str, numkeys: int, *args: Any) -> int:
        if numkeys != 1:
            raise RuntimeError("FakeRedis only supports single-key eval for lock")
        key = str(args[0])
        token = str(args[1])
        if self.kv.get(key) == token:
            self.kv.pop(key, None)
            return 1
        return 0


def test_lock_acquire_release_and_finally_close() -> None:
    from agentlz.services.cache_service import acquire_chat_lock, release_chat_lock
    from agentlz.services.agent_service import agent_chat_service

    rc = FakeRedis()
    rid = 123
    key = f"chat:lock:record:{rid}"

    with patch("agentlz.services.cache_service.get_redis_client", return_value=rc):
        ok1 = acquire_chat_lock(record_id=rid, token="t1", ttl_ms=30000)
        ok2 = acquire_chat_lock(record_id=rid, token="t2", ttl_ms=30000)
        assert ok1 is True
        assert ok2 is False
        assert rc.get(key) == "t1"
        assert release_chat_lock(record_id=rid, token="t2") is False
        assert rc.get(key) == "t1"
        assert release_chat_lock(record_id=rid, token="t1") is True
        assert rc.get(key) is None

    def _fake_rag(*, agent_id: int, message: str, record_id: int, meta=None) -> Dict[str, Any]:
        return {"record_id": int(record_id), "message": message, "doc": "", "history": ""}

    def _fake_stream(*, agent_id: int, record_id: int, out: Dict[str, Any], meta=None):
        yield f"data: {json.dumps({'record_id': int(record_id)})}\n\n"
        yield "data: hello\n\n"
        yield "data: [DONE]\n\n"

    with (
        patch("agentlz.services.cache_service.get_redis_client", return_value=rc),
        patch("agentlz.services.agent_service.agent_chat_get_rag", side_effect=_fake_rag),
        patch("agentlz.services.agent_service.agent_llm_answer_stream", side_effect=_fake_stream),
    ):
        gen = agent_chat_service(agent_id=1, message="hi", record_id=rid, meta={"request_id": "req1"})
        first = next(gen)
        assert "record_id" in first
        assert rc.get(key) == "req1"
        gen.close()
        assert rc.get(key) is None

