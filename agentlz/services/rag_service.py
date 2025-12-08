from __future__ import annotations

from agentlz.core.logger import setup_logging

"""RAG 服务层 不需鉴权, 功能: 执行 rag操作, 对message切分.

运用的表: record session
"""

from typing import Any, Dict, Optional, List
from fastapi import HTTPException

from agentlz.config.settings import get_settings
from agentlz.repositories import record_repository as repo
from agentlz.repositories import document_repository as doc_repo
from agentlz.services import document_service as doc_service
from agentlz.services import chunk_embeddings_service as emb_service
from agentlz.repositories import session_repository as sess_repo
import json


def _tables() -> Dict[str, str]:
    """获取相关表名（含默认值）

    返回：
    - 字典，包含 `record`、`session` 的表名映射。
    """
    s = get_settings()
    return {
        "record": getattr(s, "record_table_name", "record"),
        "session": getattr(s, "session_table_name", "session"),
    }


def ensure_record_belongs_to_agent_service(*, record_id: int, agent_id: int) -> Dict[str, Any]:
    """校验记录是否属于指定 Agent

    参数：
    - record_id：记录主键 ID。
    - agent_id：Agent 主键 ID。

    返回：
    - 若校验通过，返回记录字典（含 `id/agent_id/name/meta/created_at`）。
    """
    table = _tables()["record"]
    row = repo.get_record_by_id(record_id=record_id, table_name=table)
    if not row:
        raise HTTPException(status_code=404, detail="Record不存在")
    try:
        rid_agent_id = int(row.get("agent_id") or 0)
    except Exception:
        rid_agent_id = 0
    if rid_agent_id != int(agent_id):
        raise HTTPException(status_code=403, detail="Record不属于该Agent")
    return row


def get_doc_topk_messages(
    *,
    agent_id: int,
    message: str,
    limit: int = 5,
    distance_metric: str = "euclidean",
    include_vector: bool = False,
) -> list[Dict[str, Any]]:
    """根据 Agent 关联文档循环检索相似文本块 Top-K

    参数：
    - agent_id：Agent 主键 ID（上层已确保存在）
    - message：输入消息文本
    - limit：返回条数上限（全局 Top-K）
    - distance_metric：距离度量方式（euclidean 或 cosine）
    - include_vector：是否返回向量

    返回：
    - 列表，每项包含 `chunk_id/doc_id/content/similarity_score`（当 `include_vector=True` 时包含 `embedding`）
    """
    if not isinstance(message, str) or message.strip() == "":
        raise HTTPException(status_code=400, detail="message不能为空")
    if int(limit) <= 0:
        limit = 5

    s = get_settings()
    doc_table = getattr(s, "document_table_name", "document")
    user_table = getattr(s, "user_table_name", "users")
    tenant_table = getattr(s, "tenant_table_name", "tenant")

    doc_ids_grouped = doc_service.list_agent_related_document_ids_service(agent_id=int(agent_id))
    if not doc_ids_grouped:
        return []
    merged: list[Dict[str, Any]] = []
    for tid, did_list in doc_ids_grouped.items():
        results = emb_service.search_similar_chunks_service(
            tenant_id=str(tid),
            message=message,
            doc_ids=[str(x) for x in did_list],
            distance_metric=distance_metric,
            limit=limit,
            include_vector=include_vector,
        )
        if results:
            merged.extend(results)

    merged.sort(key=lambda x: float(x.get("similarity_score", 1e9)))
    return merged[:limit]



def check_all_session_detail_by_record(*, record_id: int) -> List[Dict[str, Any]]:
    """检查记录关联会话（输入/输出）

    参数：
    - record_id：记录主键 ID（上层已确保存在）

    返回：
    - 列表，每项包含 `id/count/input/output/time`（当 `meta_input/output` 为 JSON 字符串时解析为对象）
    """
    if int(record_id) <= 0:
        raise HTTPException(status_code=400, detail="record_id不合法")
    tables = _tables()
    table = tables["session"]
    rows = sess_repo.list_sessions_by_record(record_id=int(record_id), table_name=table)
    out: List[Dict[str, Any]] = []
    for r in rows:
        mi = r.get("meta_input")
        mo = r.get("meta_output")
        try:
            inp = json.loads(mi) if isinstance(mi, str) else mi
        except Exception:
            inp = mi
        try:
            outp = json.loads(mo) if isinstance(mo, str) else mo
        except Exception:
            outp = mo
        ca = r.get("created_at")
        out.append(
            {
                "id": int(r.get("id")),
                "count": int(r.get("count") or 0),
                "input": inp,
                "output": outp,
                "time": str(ca) if ca is not None else None,
            }
        )
    return out


def check_session_for_rag(*, record_id: int, limit_input: int, limit_output: int) -> List[Dict[str, Any]]:
    """检查记录关联会话（输入/输出）

    参数：
    - record_id：记录主键 ID（上层已确保存在）
    - limit_input：返回条数上限（从后往前数，0 表示不返回输入）
    - limit_output：返回条数上限（从后往前数，0 表示不返回输出）

    返回：
    - 列表，每项包含 `input/output/zip`（当 `limit_* > 0` 时包含对应值，否则为 None）
    """
    if int(record_id) <= 0:
        return []
    li = int(limit_input) if isinstance(limit_input, int) else 0
    lo = int(limit_output) if isinstance(limit_output, int) else 0
    if li < 0:
        li = 0
    if lo < 0:
        lo = 0
    tables = _tables()
    table = tables["session"]
    rows = sess_repo.list_sessions_by_record(record_id=int(record_id), table_name=table)
    n = len(rows)
    out: List[Dict[str, Any]] = []
    for idx, r in enumerate(rows):
        pos_from_end = n - idx
        mi = r.get("meta_input")
        mo = r.get("meta_output")
        z = r.get("zip")
        if pos_from_end <= li:
            try:
                inp = json.loads(mi) if isinstance(mi, str) else mi
            except Exception:
                inp = mi
        else:
            inp = None
        if pos_from_end <= lo:
            try:
                outp = json.loads(mo) if isinstance(mo, str) else mo
            except Exception:
                outp = mo
        else:
            outp = None
        out.append({"input": inp, "output": outp, "zip": z})
    return out


def agent_chat_get_rag(*, agent_id: int, message: str, record_id: int=-1) -> Dict[str, Any]:
    """ RAG 检索 部分

    参数：
    - agent_id：智能体主键 ID（上层已确保存在）
    - message：用户输入消息
    - record_id：记录主键 ID（默认 -1，记录id为0,没有历史纪录）

    返回：
    - 列表，每项包含 `similarity_score/document_id/title/description/meta_https/tags/type/claims`（当 `meta_https/tags` 为 JSON 字符串时解析为对象）
    """

    logger = setup_logging()
    logger.info('进入agent_chat_service服务')
    rag=get_doc_topk_messages(
        agent_id=int(agent_id),
        message=message,
    )
    for x in rag:
        logger.info(f"rag 得分(越小越相关): {x.get("similarity_score")}")
    history=check_session_for_rag(
        record_id=int(record_id),
        limit_input=5,
        limit_output=5,
    )
    doc_texts = []
    for x in rag:
        c = x.get("content")
        if c:
            doc_texts.append(str(c))
    doc_joined = "\n".join(doc_texts)
    his_items = []
    for x in history:
        z = x.get("zip")
        inp = x.get("input")
        outp = x.get("output")
        if inp is None or (isinstance(inp, str) and inp.strip() == ""):
            inp = ""
        if outp is None or (isinstance(outp, str) and outp.strip() == ""):
            outp = ""
        if inp is None and outp is None:
            continue
        if not isinstance(inp, str):
            try:
                inp = json.dumps(inp, ensure_ascii=False)
            except Exception:
                inp = str(inp)
        if not isinstance(outp, str):
            try:
                outp = json.dumps(outp, ensure_ascii=False)
            except Exception:
                outp = str(outp)
        his_items.append((inp or "", outp or "", z or ""))
    his_parts = []
    for i, (inp, outp, z) in enumerate(his_items, start=1):
        his_parts.append(f"第{i}轮: human:{inp}, llm:{outp}, zip:{z}")  
    his_joined = "; ".join(his_parts)
    out = {"doc": doc_joined, "history": his_joined, "message": message}
    logger.info(f"agent_chat_service_summary: {out}")
    # 已经获取到rag和history，后续可以根据需要进行处理
    return out
    

