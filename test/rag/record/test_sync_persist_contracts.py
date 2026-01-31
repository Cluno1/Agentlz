from __future__ import annotations

import json
from typing import Any, Dict
from unittest.mock import patch


class FakeResult:
    def __init__(self, lastrowid: int):
        self.lastrowid = lastrowid
        self.rowcount = 1


class FakeConn:
    def __init__(self, store: Dict[str, Any]):
        self.store = store

    def execute(self, sql, params=None):
        txt = str(sql)
        self.store["executed"].append(txt)
        if "INSERT INTO" in txt and "ON DUPLICATE KEY UPDATE" in txt:
            self.store["last_insert"] = 42
            self.store["row"] = {
                "id": 42,
                "record_id": int(params["record_id"]),
                "count": int(params["count"]),
                "meta_input": params["meta_input"],
                "meta_output": params["meta_output"],
                "zip": "",
                "request_id": params["request_id"],
                "zip_status": params["zip_status"],
                "zip_updated_at": None,
                "created_at": params["created_at"],
            }
            return FakeResult(lastrowid=42)
        if "SELECT COALESCE(MAX(count)" in txt:
            class _S:
                def scalar(self_non):
                    return 0

            return _S()
        if "SELECT id, record_id" in txt and "WHERE id = :id" in txt:
            class _R:
                def mappings(self_non):
                    return self_non

                def first(self_non):
                    return self.store["row"]

            return _R()
        if "WHERE request_id" in txt:
            class _R:
                def mappings(self_non):
                    return self_non

                def first(self_non):
                    return None

            return _R()
        raise RuntimeError(f"unexpected sql: {txt}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeEngine:
    def __init__(self, store: Dict[str, Any]):
        self.store = store

    def connect(self):
        return FakeConn(self.store)

    def begin(self):
        return FakeConn(self.store)


def test_create_session_idempotent_uses_request_id() -> None:
    from agentlz.repositories import session_repository as sess_repo

    store: Dict[str, Any] = {"executed": []}
    engine = FakeEngine(store)

    with patch("agentlz.repositories.session_repository.get_mysql_engine", return_value=engine):
        row, created = sess_repo.create_session_idempotent(
            record_id=1,
            request_id="req-1",
            meta_input={"text": "hi"},
            meta_output={"text": "ok"},
            table_name="session",
        )
        assert created is True
        assert int(row["id"]) == 42
        assert row["request_id"] == "req-1"
        assert json.loads(row["meta_input"])["text"] == "hi"
        assert "ON DUPLICATE KEY UPDATE" in "\n".join(store["executed"])

