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


def test_record_zip_worker_skips_when_up_to_date() -> None:
    from agentlz.services.mq_service import MQService

    svc = MQService()
    ch = FakeChannel()
    method = SimpleNamespace(delivery_tag=1, routing_key="zip_record_aggregate_tasks")
    props = SimpleNamespace(headers={})
    body = json.dumps({"record_id": 1, "agent_id": 1, "target_until_session_id": 5}).encode("utf-8")

    with (
        patch("agentlz.services.mq_service.acquire_record_zip_lock", return_value=True),
        patch("agentlz.services.mq_service.release_record_zip_lock", return_value=True),
        patch(
            "agentlz.services.mq_service.record_repo.get_record_summary",
            return_value={"summary_until_session_id": 10, "summary_zip": "已有", "summary_version": 1},
        ),
        patch("agentlz.services.mq_service.record_repo.update_record_summary_if_earlier") as upd,
    ):
        svc._process_record_zip_aggregate_message(ch, method, props, body)
        assert ch.acked == 1
        upd.assert_not_called()


def test_record_zip_worker_updates_summary() -> None:
    from agentlz.services.mq_service import MQService

    svc = MQService()
    ch = FakeChannel()
    method = SimpleNamespace(delivery_tag=1, routing_key="zip_record_aggregate_tasks")
    props = SimpleNamespace(headers={})
    body = json.dumps({"record_id": 9, "agent_id": 1, "target_until_session_id": 2}).encode("utf-8")

    rows = [
        {
            "id": 1,
            "record_id": 9,
            "count": 1,
            "meta_input": json.dumps({"text": "你好"}, ensure_ascii=False),
            "meta_output": json.dumps({"text": "世界"}, ensure_ascii=False),
            "zip": "摘要A",
            "zip_status": "done",
            "created_at": "now",
        },
        {
            "id": 2,
            "record_id": 9,
            "count": 2,
            "meta_input": json.dumps({"text": "再来"}, ensure_ascii=False),
            "meta_output": json.dumps({"text": "回答"}, ensure_ascii=False),
            "zip": "",
            "zip_status": "pending",
            "created_at": "now",
        },
    ]

    class FakeChain:
        def invoke(self, data):
            return SimpleNamespace(content="总摘要")

    class FakePrompt:
        def __or__(self, other):
            return FakeChain()

    with (
        patch("agentlz.services.mq_service.acquire_record_zip_lock", return_value=True),
        patch("agentlz.services.mq_service.release_record_zip_lock", return_value=True),
        patch(
            "agentlz.services.mq_service.record_repo.get_record_summary",
            return_value={"summary_until_session_id": 0, "summary_zip": "", "summary_version": 1},
        ),
        patch("agentlz.services.mq_service.sess_repo.list_sessions_in_id_range", return_value=rows),
        patch("agentlz.services.mq_service.agent_repo.get_agent_by_id_any_tenant", return_value={"meta": "{}"}),
        patch("agentlz.services.mq_service.get_model", return_value=object()),
        patch("agentlz.services.mq_service.ChatPromptTemplate.from_messages", return_value=FakePrompt()),
        patch("agentlz.services.mq_service.record_repo.update_record_summary_if_earlier", return_value=True) as upd,
    ):
        svc._process_record_zip_aggregate_message(ch, method, props, body)
        assert ch.acked == 1
        upd.assert_called_once()
