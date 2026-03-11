from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from io import BytesIO
import json
import time
import pandas as pd
from fastapi import HTTPException
from agentlz.config.settings import get_settings
from agentlz.core.logger import setup_logging
from agentlz.core.external_services import publish_to_rabbitmq
from agentlz.core.ws_manager import get_ws_manager
from agentlz.repositories import evaluation_repository as eva_repo
from agentlz.repositories import agent_repository as agent_repo
from agentlz.services import agent_service

logger = setup_logging()


def _tables() -> Tuple[str, str, str]:
    """
    读取测评相关表名配置。

    参数：
    - 无，内部读取 settings.py。

    返回：
    - (eva_json_table, eva_version_table, eva_content_table)。
    """
    s = get_settings()
    return (
        getattr(s, "eva_json_table_name", "eva_json"),
        getattr(s, "eva_version_table_name", "eva_version"),
        getattr(s, "eva_content_table_name", "eva_content"),
    )


def _now() -> datetime:
    """
    获取东八区当前时间。

    参数：
    - 无。

    返回：
    - timezone aware datetime。
    """
    return datetime.now(timezone(timedelta(hours=8)))


def _current_user_id(claims: Optional[Dict[str, Any]]) -> int:
    """
    从鉴权 claims 提取当前用户ID。

    参数：
    - claims：JWT 声明字典，必须包含 sub。

    返回：
    - 当前用户ID（int）。

    边界条件：
    - claims 缺失或非法时抛出 401。
    """
    if not claims or not isinstance(claims, dict):
        raise HTTPException(status_code=401, detail="缺少或非法的 Authorization 头")
    try:
        return int(claims.get("sub") or 0)
    except Exception:
        return 0


def _resolve_scope_tenant(type_value: Optional[str], tenant_id: str) -> str:
    """
    根据 type 解析目标租户ID。

    参数：
    - type_value：self/tenant/system。
    - tenant_id：当前请求租户ID。

    返回：
    - 最终落库/查询租户ID。
    """
    if str(type_value or "tenant") == "self":
        return "default"
    if str(type_value or "tenant") == "system":
        return "system"
    return str(tenant_id)


def _serialize_time_fields(row: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    """
    将时间字段标准化为字符串，便于前端消费。

    参数：
    - row：单条记录。
    - keys：需要序列化的时间字段名列表。

    返回：
    - 同一个字典对象（原地修改后返回）。
    """
    for k in keys:
        if row.get(k) is not None:
            row[k] = str(row[k])
    return row


def _normalize_text(text: Optional[str]) -> str:
    """
    规范化文本用于打分比较。

    参数：
    - text：任意文本。

    返回：
    - 小写、去换行、去首尾空白后的文本。
    """
    return str(text or "").lower().replace("\r", " ").replace("\n", " ").strip()


def _alpaca_items_from_any(raw: Any) -> Tuple[List[Dict[str, Any]], bool]:
    """
    将任意 JSON 结构规范化为 Alpaca-like 列表。

    参数：
    - raw：任意 JSON 对象/数组。

    返回：
    - (items, is_alpaca)：
      - items：转换后的统一样本列表；
      - is_alpaca：输入是否已满足 alpaca 结构。
    """
    if isinstance(raw, list):
        normalized: List[Dict[str, Any]] = []
        alpaca = True
        for item in raw:
            if not isinstance(item, dict):
                alpaca = False
                normalized.append(
                    {
                        "instruction": "",
                        "input": str(item or ""),
                        "output": "",
                    }
                )
                continue
            instruction = str(item.get("instruction") or "")
            input_text = str(item.get("input") or item.get("question") or item.get("query") or "")
            output_text = str(
                item.get("output")
                or item.get("answer")
                or item.get("expected")
                or item.get("expect_output")
                or ""
            )
            if "instruction" not in item and "input" not in item and "output" not in item:
                alpaca = False
            normalized.append(
                {
                    "instruction": instruction,
                    "input": input_text,
                    "output": output_text,
                }
            )
        return normalized, alpaca
    if isinstance(raw, dict):
        if isinstance(raw.get("data"), list):
            return _alpaca_items_from_any(raw.get("data"))
        text = json.dumps(raw, ensure_ascii=False)
        return [{"instruction": "", "input": text, "output": ""}], False
    return [{"instruction": "", "input": str(raw or ""), "output": ""}], False


def _consume_agent_output(agent_id: int, message: str, user_id: str) -> str:
    """
    调用 Agent 对话链路并提取最终文本输出。

    参数：
    - agent_id：目标 Agent ID。
    - message：用户输入文本。
    - user_id：当前用户ID（字符串）。

    返回：
    - 聚合后的模型输出文本。
    """
    gen = agent_service.agent_chat_service(
        agent_id=int(agent_id),
        message=str(message or ""),
        meta={"user_id": str(user_id)},
    )
    parts: List[str] = []
    for chunk in gen:
        if not isinstance(chunk, str):
            continue
        for line in chunk.splitlines():
            if not line.startswith("data:"):
                continue
            data = line.replace("data:", "", 1).strip()
            if data == "[DONE]":
                return "\n".join(parts).strip()
            if not data:
                continue
            try:
                obj = json.loads(data)
                if isinstance(obj, dict):
                    continue
            except Exception:
                pass
            parts.append(data)
    return "\n".join(parts).strip()


def _publish_ws(topic: str, payload: Dict[str, Any]) -> None:
    """
    向 WebSocket topic 推送消息。

    参数：
    - topic：订阅主题。
    - payload：推送消息体。

    返回：
    - 无。
    """
    manager = get_ws_manager()
    fut = manager.submit(manager.publish(topic, payload))
    if fut is None:
        return


def list_evaluation_datasets_service(
    *,
    page: int,
    per_page: int,
    sort: str,
    order: str,
    q: Optional[str],
    type: str,
    tenant_id: str,
    claims: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    分页查询测评数据集列表。

    参数：
    - page/per_page/sort/order/q：分页与检索参数。
    - type：self/tenant/system，决定查询租户。
    - tenant_id：当前请求租户。
    - claims：鉴权信息。

    返回：
    - (rows, total)。
    """
    _current_user_id(claims)
    dataset_table, _, _ = _tables()
    dataset_tenant = _resolve_scope_tenant(type, tenant_id)
    rows, total = eva_repo.list_eva_datasets(
        page=page,
        per_page=per_page,
        sort=sort,
        order=order,
        q=q,
        tenant_id=dataset_tenant,
        table_name=dataset_table,
    )
    for row in rows:
        _serialize_time_fields(row, ["created_at", "updated_at"])
    return rows, total


def get_evaluation_dataset_service(
    *, dataset_id: str, type: str, tenant_id: str, claims: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    查询单个测评数据集详情。

    参数：
    - dataset_id：数据集ID。
    - type：self/tenant/system。
    - tenant_id：当前租户。
    - claims：鉴权信息。

    返回：
    - 命中返回数据集详情，否则返回 None。
    """
    _current_user_id(claims)
    dataset_table, _, _ = _tables()
    dataset_tenant = _resolve_scope_tenant(type, tenant_id)
    row = eva_repo.get_eva_dataset_by_id(dataset_id=dataset_id, tenant_id=dataset_tenant, table_name=dataset_table)
    if not row:
        return None
    return _serialize_time_fields(row, ["created_at", "updated_at"])


def delete_evaluation_dataset_service(
    *, dataset_id: str, type: str, tenant_id: str, claims: Optional[Dict[str, Any]] = None
) -> bool:
    """
    删除测评数据集。

    参数：
    - dataset_id：数据集ID。
    - type：self/tenant/system。
    - tenant_id：当前租户。
    - claims：鉴权信息。

    返回：
    - 删除成功返回 True，未命中返回 False。
    """
    _current_user_id(claims)
    dataset_table, _, _ = _tables()
    dataset_tenant = _resolve_scope_tenant(type, tenant_id)
    return eva_repo.delete_eva_dataset(dataset_id=dataset_id, tenant_id=dataset_tenant, table_name=dataset_table)


def create_evaluation_dataset_service(
    *,
    name: str,
    type: str,
    status: Optional[str],
    data_json: Any,
    tenant_id: str,
    claims: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    创建测评数据集（eva_json）。

    参数：
    - name：测评集名称。
    - type：self/tenant/system。
    - status：可选状态。
    - data_json：测评数据JSON（对象或字符串）。
    - tenant_id：当前请求租户。
    - claims：鉴权信息。

    返回：
    - 创建后的数据集记录。
    """
    user_id = _current_user_id(claims)
    dataset_table, _, _ = _tables()
    dataset_tenant = _resolve_scope_tenant(type, tenant_id)
    if isinstance(data_json, str):
        try:
            parsed = json.loads(data_json)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="data_json 不是有效JSON") from exc
    else:
        parsed = data_json
    items, is_alpaca = _alpaca_items_from_any(parsed)
    row = eva_repo.create_eva_dataset(
        payload={
            "name": str(name or "").strip() or "evaluation_dataset",
            "scope": str(type or "tenant"),
            "status": str(status or ("ready" if is_alpaca else "raw")),
            "data_json": json.dumps(items, ensure_ascii=False),
            "total_count": len(items),
            "uploaded_by_user_id": user_id,
        },
        tenant_id=dataset_tenant,
        table_name=dataset_table,
    )
    return _serialize_time_fields(row, ["created_at", "updated_at"])


def parse_alpaca_placeholder_service(
    *, raw_json: Any, hint: Optional[str], claims: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    占位实现：将非 alpaca JSON 转换为 alpaca 格式。

    参数：
    - raw_json：原始 JSON 数据。
    - hint：可选提示词，当前仅透传返回。
    - claims：鉴权信息。

    返回：
    - {is_alpaca, items, hint}。
    """
    _current_user_id(claims)
    items, is_alpaca = _alpaca_items_from_any(raw_json)
    return {"is_alpaca": is_alpaca, "items": items, "hint": str(hint or "")}


def _snapshot_agent_for_version(
    *, agent_id: int, tenant_id: str, claims: Optional[Dict[str, Any]]
) -> Dict[str, str]:
    """
    读取 Agent 当前配置并构造版本快照 JSON 字段。

    参数：
    - agent_id：目标 Agent ID。
    - tenant_id：当前租户。
    - claims：鉴权信息。

    返回：
    - {prompt, document_ids_json, strategy_json, mcp_json}。
    """
    agent = agent_service.get_agent_service(agent_id=int(agent_id), tenant_id=tenant_id, claims=claims)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent不存在")
    documents = agent.get("documents") or []
    document_ids: List[str] = []
    strategy_map: Dict[str, Any] = {}
    for doc in documents:
        did = str(doc.get("id") or "")
        if not did:
            continue
        document_ids.append(did)
        strategy_map[did] = doc.get("strategy")
    mcp_json = json.dumps(agent.get("mcp_agents") or [], ensure_ascii=False)
    prompt = str(agent.get("system_prompt") or agent.get("prompt") or "")
    return {
        "prompt": prompt,
        "document_ids_json": json.dumps(document_ids, ensure_ascii=False),
        "strategy_json": json.dumps(strategy_map, ensure_ascii=False),
        "mcp_json": mcp_json,
    }


def start_evaluation_service(
    *, eva_json_id: str, agent_id: int, type: Optional[str], tenant_id: str, claims: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    启动测评任务并创建版本快照与结果记录。

    参数：
    - eva_json_id：测评数据集ID。
    - agent_id：Agent ID。
    - type：可选 self/tenant/system，决定数据集租户。
    - tenant_id：当前租户。
    - claims：鉴权信息。

    返回：
    - {status, eva_content_id, eva_version_id}。
    """
    user_id = _current_user_id(claims)
    dataset_table, version_table, content_table = _tables()
    dataset_tenant = _resolve_scope_tenant(type or "tenant", tenant_id)
    dataset = eva_repo.get_eva_dataset_by_id(dataset_id=eva_json_id, tenant_id=dataset_tenant, table_name=dataset_table)
    if not dataset:
        raise HTTPException(status_code=404, detail="测评集不存在")
    agent_row = agent_service.ensure_agent_access_service(agent_id=int(agent_id), tenant_id=tenant_id, claims=claims)
    try:
        existing_version_id = int(agent_row.get("eva_version_id") or 0)
    except Exception:
        existing_version_id = 0
    eva_version_id = existing_version_id
    if eva_version_id <= 0:
        snapshot = _snapshot_agent_for_version(agent_id=int(agent_id), tenant_id=tenant_id, claims=claims)
        version = eva_repo.create_eva_version(
            payload={
                "agent_id": int(agent_id),
                "created_by_user_id": user_id,
                "prompt": snapshot["prompt"],
                "document_ids_json": snapshot["document_ids_json"],
                "strategy_json": snapshot["strategy_json"],
                "mcp_json": snapshot["mcp_json"],
            },
            tenant_id=dataset_tenant,
            table_name=version_table,
        )
        try:
            eva_version_id = int(version.get("id") or 0)
        except Exception:
            eva_version_id = 0
        if eva_version_id > 0 and agent_row.get("id") is not None:
            try:
                s = get_settings()
                agent_table_name = getattr(s, "agent_table_name", "agent")
                agent_repo.update_agent_no_read(
                    agent_id=int(agent_row["id"]),
                    payload={"eva_version_id": int(eva_version_id)},
                    tenant_id=str(agent_row.get("tenant_id") or tenant_id),
                    table_name=agent_table_name,
                )
            except Exception as e:
                logger.error(
                    f"start_evaluation_service update eva_version_id failed agent_id={agent_row.get('id')} error={e}"
                )
    total_count = int(dataset.get("total_count") or 0)
    content = eva_repo.create_eva_content(
        payload={
            "eva_json_id": str(eva_json_id),
            "eva_version_id": int(eva_version_id or 0),
            "status": "queued",
            "total_count": total_count,
            "completed_count": 0,
            "content_json": "[]",
            "started_at": None,
            "finished_at": None,
        },
        tenant_id=dataset_tenant,
        table_name=content_table,
    )
    publish_to_rabbitmq(
        "eva_eval_tasks",
        {
            "eva_json_id": str(eva_json_id),
            "eva_version_id": int(eva_version_id or 0),
            "eva_content_id": int(content.get("id") or 0),
            "agent_id": int(agent_id),
            "tenant_id": dataset_tenant,
            "user_id": str(user_id),
            "offset": 0,
            "batch_size": 10,
        },
        durable=True,
    )
    return {
        "status": "queued",
        "eva_content_id": int(content.get("id") or 0),
        "eva_version_id": int(eva_version_id or 0),
    }


def list_agent_versions_service(
    *,
    agent_id: int,
    tenant_id: str,
    page: int,
    per_page: int,
    sort: str,
    order: str,
    claims: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    查询指定 Agent 的版本历史。

    参数：
    - agent_id：Agent ID。
    - tenant_id：当前租户。
    - page/per_page/sort/order：分页排序参数。
    - claims：鉴权信息。

    返回：
    - (rows, total)。
    """
    _current_user_id(claims)
    _, version_table, _ = _tables()
    rows, total = eva_repo.list_eva_versions(
        agent_id=int(agent_id),
        tenant_id=tenant_id,
        page=page,
        per_page=per_page,
        sort=sort,
        order=order,
        table_name=version_table,
    )
    for row in rows:
        _serialize_time_fields(row, ["created_at", "updated_at"])
    return rows, total


def list_agent_contents_service(
    *,
    agent_id: int,
    eva_version_id: Optional[int],
    tenant_id: str,
    page: int,
    per_page: int,
    sort: str,
    order: str,
    claims: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    查询指定 Agent 的测评运行结果列表。

    参数：
    - agent_id：Agent ID。
    - eva_version_id：可选版本过滤。
    - tenant_id：当前租户。
    - page/per_page/sort/order：分页排序参数。
    - claims：鉴权信息。

    返回：
    - (rows, total)。
    """
    _current_user_id(claims)
    _, version_table, content_table = _tables()
    rows, total = eva_repo.list_eva_contents(
        tenant_id=tenant_id,
        agent_id=int(agent_id),
        eva_version_id=eva_version_id,
        page=page,
        per_page=per_page,
        sort=sort,
        order=order,
        content_table_name=content_table,
        version_table_name=version_table,
    )
    for row in rows:
        _serialize_time_fields(row, ["started_at", "finished_at", "created_at", "updated_at"])
    return rows, total


def get_content_detail_service(
    *, content_id: int, tenant_id: str, claims: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    查询单次测评结果详情。

    参数：
    - content_id：测评结果ID。
    - tenant_id：当前租户。
    - claims：鉴权信息。

    返回：
    - 命中返回详情，不存在返回 None。
    """
    _current_user_id(claims)
    _, _, content_table = _tables()
    row = eva_repo.get_eva_content_by_id(content_id=int(content_id), tenant_id=tenant_id, table_name=content_table)
    if not row:
        return None
    return _serialize_time_fields(row, ["started_at", "finished_at", "created_at", "updated_at"])


def process_evaluation_task(
    *,
    eva_json_id: str,
    eva_version_id: int,
    eva_content_id: int,
    agent_id: int,
    tenant_id: str,
    user_id: str,
    offset: int = 0,
    batch_size: int = 10,
) -> Dict[str, Any]:
    """
    执行测评任务批处理逻辑（offset 模式）。

    参数：
    - eva_json_id：测评集ID。
    - eva_version_id：版本ID。
    - eva_content_id：结果ID。
    - agent_id：Agent ID。
    - tenant_id：租户ID。
    - user_id：用户ID（用于 WS topic）。
    - offset：本轮处理起始偏移。
    - batch_size：本轮最多处理条数。

    返回：
    - 当前批次执行摘要，包含 next_offset/remaining。
    """
    dataset_table, _, content_table = _tables()
    dataset = eva_repo.get_eva_dataset_by_id(dataset_id=eva_json_id, tenant_id=tenant_id, table_name=dataset_table)
    if not dataset:
        raise HTTPException(status_code=404, detail="测评集不存在")
    content = eva_repo.get_eva_content_by_id(content_id=int(eva_content_id), tenant_id=tenant_id, table_name=content_table)
    if not content:
        raise HTTPException(status_code=404, detail="测评结果不存在")
    try:
        items = json.loads(str(dataset.get("data_json") or "[]"))
        if not isinstance(items, list):
            items = []
    except Exception:
        items = []
    total = int(len(items))
    safe_batch_size = max(1, int(batch_size or 10))
    safe_offset = max(0, int(offset or 0))
    topic = f"evaluation:user:{user_id}"
    if str(content.get("status") or "") in ("queued", "failed"):
        eva_repo.update_eva_content(
            content_id=int(eva_content_id),
            tenant_id=tenant_id,
            payload={"status": "running", "started_at": _now(), "total_count": total, "updated_at": _now()},
            table_name=content_table,
        )
    if safe_offset == 0:
        _publish_ws(
            topic,
            {
                "type": "evaluation.started",
                "topic": topic,
                "data": {"total": total, "eva_content_id": int(eva_content_id)},
            },
        )
    current_batch = items[safe_offset : safe_offset + safe_batch_size]
    if not current_batch and safe_offset >= total:
        eva_repo.update_eva_content(
            content_id=int(eva_content_id),
            tenant_id=tenant_id,
            payload={"status": "done", "completed_count": total, "finished_at": _now(), "updated_at": _now()},
            table_name=content_table,
        )
        _publish_ws(
            topic,
            {
                "type": "evaluation.done",
                "topic": topic,
                "data": {"total": total, "eva_content_id": int(eva_content_id)},
            },
        )
        return {"eva_content_id": int(eva_content_id), "remaining": 0, "next_offset": safe_offset}
    finished_items: List[Dict[str, Any]] = []
    completed_count = int(content.get("completed_count") or 0)
    for sample in current_batch:
        sample_dict = sample if isinstance(sample, dict) else {}
        instruction = str(sample_dict.get("instruction") or "")
        input_text = str(sample_dict.get("input") or "")
        expected = str(sample_dict.get("output") or "")
        prompt_text = "\n".join([x for x in [instruction, input_text] if x]).strip()
        if not prompt_text:
            prompt_text = expected
        start_at = time.time()
        fact_output = _consume_agent_output(agent_id=int(agent_id), message=prompt_text, user_id=str(user_id))
        _ = int((time.time() - start_at) * 1000)
        score = 100 if _normalize_text(fact_output) == _normalize_text(expected) and expected else 0
        opinion = "占位评审：输出与期望完全一致，得分100" if score == 100 else "占位评审：输出与期望不一致，得分0"
        result_item = {
            "instruction": instruction,
            "input": input_text,
            "output": expected,
            "fact_output": fact_output,
            "score": score,
            "opinion": opinion,
        }
        finished_items.append(result_item)
        completed_count += 1
        _publish_ws(
            topic,
            {
                "type": "evaluation.item_done",
                "topic": topic,
                "data": {
                    "eva_content_id": int(eva_content_id),
                    "completed_count": completed_count,
                    "total_count": total,
                    "item": result_item,
                },
            },
        )
    eva_repo.append_eva_content_items(
        content_id=int(eva_content_id),
        tenant_id=tenant_id,
        new_items=finished_items,
        completed_count=completed_count,
        table_name=content_table,
    )
    next_offset = safe_offset + len(current_batch)
    remaining = max(0, total - next_offset)
    if remaining > 0:
        publish_to_rabbitmq(
            "eva_eval_tasks",
            {
                "eva_json_id": str(eva_json_id),
                "eva_version_id": int(eva_version_id),
                "eva_content_id": int(eva_content_id),
                "agent_id": int(agent_id),
                "tenant_id": str(tenant_id),
                "user_id": str(user_id),
                "offset": int(next_offset),
                "batch_size": int(safe_batch_size),
            },
            durable=True,
        )
        return {"eva_content_id": int(eva_content_id), "remaining": remaining, "next_offset": next_offset}
    eva_repo.update_eva_content(
        content_id=int(eva_content_id),
        tenant_id=tenant_id,
        payload={"status": "done", "completed_count": total, "finished_at": _now(), "updated_at": _now()},
        table_name=content_table,
    )
    _publish_ws(
        topic,
        {
            "type": "evaluation.done",
            "topic": topic,
            "data": {"total": total, "eva_content_id": int(eva_content_id)},
        },
    )
    return {"eva_content_id": int(eva_content_id), "remaining": 0, "next_offset": next_offset}


def parse_evaluation_doc_task(*, eva_doc_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    兼容保留：旧版 eva_parse_tasks 占位处理函数。

    参数：
    - eva_doc_id：旧版测评文档ID。
    - tenant_id：租户ID。

    返回：
    - 固定占位结果，不再执行旧表解析逻辑。
    """
    logger.warning(f"parse_evaluation_doc_task 已废弃，忽略消息 eva_doc_id={eva_doc_id} tenant_id={tenant_id}")
    return {"deprecated": True, "eva_doc_id": str(eva_doc_id)}


def create_evaluation_doc_service(
    *,
    file_bytes: bytes,
    filename: str,
    document_type: str,
    title: Optional[str],
    description: Optional[str],
    type: str,
    tenant_id: str,
    claims: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    兼容保留：从文件创建测评集（供旧上传入口继续可用）。

    参数：
    - file_bytes：文件字节。
    - filename：文件名。
    - document_type：文件类型（csv/xlsx/json/txt 等）。
    - title/description：展示信息。
    - type：self/tenant/system。
    - tenant_id：当前租户。
    - claims：鉴权信息。

    返回：
    - 转换后创建的数据集记录。
    """
    _current_user_id(claims)
    doc_type = str(document_type or "").lower().strip()
    parsed: Any = []
    if doc_type in ("json",):
        try:
            parsed = json.loads(file_bytes.decode("utf-8"))
        except Exception:
            parsed = []
    elif doc_type in ("csv", "xlsx", "xls"):
        try:
            if doc_type == "csv":
                df = pd.read_csv(BytesIO(file_bytes)).fillna("")
            else:
                df = pd.read_excel(BytesIO(file_bytes), engine="openpyxl").fillna("")
            parsed_rows: List[Dict[str, Any]] = []
            cols = [str(c) for c in df.columns]
            first = cols[0] if cols else ""
            second = cols[1] if len(cols) > 1 else ""
            for _, row in df.iterrows():
                parsed_rows.append(
                    {
                        "instruction": "",
                        "input": str(row.get(first) or ""),
                        "output": str(row.get(second) or ""),
                    }
                )
            parsed = parsed_rows
        except Exception:
            parsed = []
    else:
        parsed = [{"instruction": "", "input": file_bytes.decode("utf-8", errors="ignore"), "output": ""}]
    return create_evaluation_dataset_service(
        name=str(title or filename or "evaluation_dataset"),
        type=type,
        status=None,
        data_json=parsed,
        tenant_id=tenant_id,
        claims=claims,
    )
