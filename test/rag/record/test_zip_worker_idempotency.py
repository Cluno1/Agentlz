from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch


class FakeChannel:
    def __init__(self):
        self.acked = 0
        self.published = 0

    def basic_ack(self, delivery_tag=None):
        self.acked += 1

    def basic_publish(self, exchange: str, routing_key: str, body: bytes, properties=None):
        self.published += 1


def test_zip_worker_skips_when_already_done() -> None:
    from agentlz.services.mq_service import MQService

    svc = MQService()
    ch = FakeChannel()
    method = SimpleNamespace(delivery_tag=1, routing_key="zip_tasks")
    props = SimpleNamespace(headers={})
    body = json.dumps({"session_id": 1, "record_id": 1, "agent_id": 1, "request_id": "r"}).encode("utf-8")

    with (
        patch("agentlz.services.mq_service.sess_repo.get_session_by_id", return_value={"id": 1, "zip": "已有", "zip_status": "done"}),
        patch("agentlz.services.mq_service.sess_repo.update_session_zip_if_pending") as upd,
    ):
        svc._process_zip_task(ch, method, props, body)
        assert ch.acked == 1
        upd.assert_not_called()


def test_zip_worker_updates_when_pending() -> None:
    from agentlz.services.mq_service import MQService

    svc = MQService()
    ch = FakeChannel()
    method = SimpleNamespace(delivery_tag=1, routing_key="zip_tasks")
    props = SimpleNamespace(headers={})
    body = json.dumps({"session_id": 2, "record_id": 9, "agent_id": 1, "request_id": "r2"}).encode("utf-8")
    row = {
        "id": 2,
        "record_id": 9,
        "count": 1,
        "meta_input": json.dumps({"text": "你好"}, ensure_ascii=False),
        "meta_output": json.dumps({"text": "世界"}, ensure_ascii=False),
        "zip": "",
        "zip_status": "pending",
        "created_at": "now",
    }

    class FakeChain:
        def invoke(self, data):
            return SimpleNamespace(content="压缩摘要")

    class FakePrompt:
        def __or__(self, other):
            return FakeChain()

    with (
        patch("agentlz.services.mq_service.sess_repo.get_session_by_id", return_value=row),
        patch("agentlz.services.mq_service.agent_repo.get_agent_by_id_any_tenant", return_value={"meta": "{}"}),
        patch("agentlz.services.mq_service.get_model", return_value=object()),
        patch("agentlz.services.mq_service.ChatPromptTemplate.from_messages", return_value=FakePrompt()),
        patch("agentlz.services.mq_service.sess_repo.update_session_zip_if_pending", return_value=True) as upd,
        patch("agentlz.services.mq_service.chat_history_set_item", return_value=True) as set_item,
    ):
        svc._process_zip_task(ch, method, props, body)
        assert ch.acked == 1
        upd.assert_called_once()
        set_item.assert_called_once()

