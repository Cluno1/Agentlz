from __future__ import annotations

import json
from typing import Any, Dict, List
from unittest.mock import patch


class FakePipeline:
    def __init__(self, rc: "FakeRedis"):
        self.rc = rc
        self.ops: List[tuple[str, tuple[Any, ...], Dict[str, Any]]] = []

    def delete(self, key: str):
        self.ops.append(("delete", (key,), {}))
        return self

    def rpush(self, key: str, *values: str):
        self.ops.append(("rpush", (key, *values), {}))
        return self

    def hset(self, key: str, mapping: Dict[str, str] | None = None):
        self.ops.append(("hset", (key,), {"mapping": mapping or {}}))
        return self

    def expire(self, key: str, ttl: int):
        self.ops.append(("expire", (key, ttl), {}))
        return self

    def execute(self):
        for name, args, kwargs in self.ops:
            getattr(self.rc, name)(*args, **kwargs)
        self.ops.clear()
        return True


class FakeRedis:
    def __init__(self):
        self.kv: Dict[str, str] = {}
        self.lists: Dict[str, List[str]] = {}
        self.hashes: Dict[str, Dict[str, str]] = {}

    def ping(self) -> bool:
        return True

    def pipeline(self) -> FakePipeline:
        return FakePipeline(self)

    def delete(self, key: str) -> int:
        existed = 0
        if key in self.kv:
            existed += 1
            self.kv.pop(key, None)
        if key in self.lists:
            existed += 1
            self.lists.pop(key, None)
        if key in self.hashes:
            existed += 1
            self.hashes.pop(key, None)
        return existed

    def expire(self, key: str, ttl: int) -> bool:
        return True

    def lrange(self, key: str, start: int, end: int) -> List[str]:
        data = self.lists.get(key, [])
        if start < 0:
            start = max(0, len(data) + start)
        if end < 0:
            end = len(data) + end
        end = min(len(data) - 1, end)
        if start > end or not data:
            return []
        return data[start : end + 1]

    def hmget(self, key: str, keys: List[str]) -> List[str | None]:
        h = self.hashes.get(key, {})
        return [h.get(k) for k in keys]

    def hset(self, key: str, mapping: Dict[str, str]):
        h = self.hashes.setdefault(key, {})
        h.update(mapping)
        return True

    def hdel(self, key: str, *fields: str) -> int:
        h = self.hashes.get(key, {})
        cnt = 0
        for f in fields:
            if f in h:
                h.pop(f, None)
                cnt += 1
        return cnt

    def rpush(self, key: str, *values: str) -> int:
        lst = self.lists.setdefault(key, [])
        lst.extend([str(v) for v in values])
        return len(lst)

    def ltrim(self, key: str, start: int, end: int) -> bool:
        data = self.lists.get(key, [])
        if not data:
            return True
        if start < 0:
            start = max(0, len(data) + start)
        if end < 0:
            end = len(data) + end
        end = min(len(data) - 1, end)
        if start > end:
            self.lists[key] = []
        else:
            self.lists[key] = data[start : end + 1]
        return True

    def eval(self, script: str, numkeys: int, *args: Any) -> int:
        if numkeys != 3:
            raise RuntimeError("FakeRedis only supports 3-key eval for history append")
        ids_key = str(args[0])
        map_key = str(args[1])
        meta_key = str(args[2])
        sid = str(args[3])
        json_value = str(args[4])
        limit = int(args[5])
        ttl = int(args[6])
        new_len = self.rpush(ids_key, sid)
        self.hset(map_key, mapping={sid: json_value})
        if new_len > limit:
            trim_count = new_len - limit
            old_ids = self.lrange(ids_key, 0, trim_count - 1)
            self.ltrim(ids_key, trim_count, -1)
            if old_ids:
                self.hdel(map_key, *old_ids)
        self.expire(ids_key, ttl)
        self.expire(map_key, ttl)
        self.expire(meta_key, ttl)
        return 1


def test_history_append_trim_and_read() -> None:
    from agentlz.services.cache_service import chat_history_append, chat_history_get

    rc = FakeRedis()
    rid = 1
    ids_key = f"chat:history:{rid}:ids"
    map_key = f"chat:history:{rid}:map"

    with patch("agentlz.services.cache_service.get_redis_client", return_value=rc):
        for i in range(60):
            sid = i + 1
            item = {"session_id": sid, "count": sid, "input": {"text": f"in{sid}"}, "output": {"text": f"out{sid}"}, "zip": "", "zip_status": "pending"}
            assert chat_history_append(record_id=rid, session_id=sid, item=item, ttl=3600, limit=50) is True

        ids = rc.lrange(ids_key, 0, -1)
        assert len(ids) == 50
        assert ids[0] == "11"
        assert ids[-1] == "60"
        assert "1" not in rc.hashes.get(map_key, {})
        assert "10" not in rc.hashes.get(map_key, {})
        assert "11" in rc.hashes.get(map_key, {})

        got = chat_history_get(record_id=rid, limit=50)
        assert len(got) == 50
        assert got[0]["session_id"] == 11
        assert got[-1]["session_id"] == 60


def test_check_session_for_rag_fallback_populates_cache() -> None:
    from agentlz.services.rag.rag_service import check_session_for_rag

    rows = [
        {
            "id": 1,
            "record_id": 9,
            "count": 1,
            "meta_input": json.dumps({"text": "a"}, ensure_ascii=False),
            "meta_output": json.dumps({"text": "b"}, ensure_ascii=False),
            "zip": "",
            "zip_status": "pending",
            "created_at": "t",
        }
    ]

    with (
        patch("agentlz.services.rag.rag_service.chat_history_get", return_value=[]),
        patch("agentlz.services.rag.rag_service.chat_history_overwrite", return_value=True) as ow,
        patch("agentlz.services.rag.rag_service.sess_repo.list_last_sessions", return_value=rows),
    ):
        out = check_session_for_rag(record_id=9, limit_input=5, limit_output=5)
        assert out[0]["input"]["text"] == "a"
        assert out[0]["output"]["text"] == "b"
        ow.assert_called_once()
