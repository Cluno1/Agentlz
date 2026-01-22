from __future__ import annotations

from agentlz.core.logger import setup_logging

"""RAG 服务层 不需鉴权, 功能: 执行 rag操作, 对message切分.

运用的表: record session
"""

from typing import Any, Dict, Optional, List, Tuple
from fastapi import HTTPException

from agentlz.config.settings import get_settings
from agentlz.repositories import record_repository as repo
from agentlz.repositories import document_repository as doc_repo
from agentlz.services.rag import document_service as doc_service
from agentlz.services.rag import chunk_embeddings_service as emb_service
from agentlz.repositories import session_repository as sess_repo
import json
from agentlz.agents.rag.rag_agent import get_rag_query_agent, rag_build_queries
from agentlz.schemas.rag import RAGQueryInput, RAGQueryOutput
from agentlz.core.external_services import get_redis_client
import time
import uuid


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
    logger = setup_logging(level="DEBUG", name="agentlz.rag_service", prefix="[RAG 服务]")
    logger.debug(f"进入 [ensure_record_belongs_to_agent_service] record_id={record_id} agent_id={agent_id}")
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
    logger.debug(f"完成 [ensure_record_belongs_to_agent_service] record_id={record_id}")
    return row


def get_list_records_by_meta_and_agent_id(
    *,
    agent_id: int,
    page: int = 1,
    per_page: int = 10,
    meta_keyword: Optional[str] = None,
    ) -> Dict[str, Any]:
    """分页查询 Record（按 agent_id 与 meta 关键字）

    参数：
    - agent_id：Agent 主键 ID
    - page：页码（从 1 开始，默认 1）
    - per_page：每页条数（默认 10）
    - meta_keyword：基于 `meta` 的关键字模糊匹配（LIKE），为空时忽略

    行为：
    - 默认按 `created_at` 倒序（DESC）返回

    返回：
    - 字典：`{"rows": List[Dict], "total": int}`
      - `rows` 每行包含：`id/agent_id/name/created_at`
    """
    tables = _tables()
    table = tables["record"]
    # 调用仓储层 SQL，按条件分页查询
    rows, total = repo.list_records_by_meta_and_agent_id(
        agent_id=int(agent_id),
        meta_keyword=meta_keyword,
        page=max(1, int(page)),
        per_page=max(1, int(per_page)),
        sort="createdAt",
        order="DESC",
        table_name=table,
    )
    return {"rows": rows, "total": int(total)}


def get_list_records_by_name_and_agent_id(
    *,
    agent_id: int,
    page: int = 1,
    per_page: int = 10,
    keyword: Optional[str] = None,
) -> Dict[str, Any]:
    tables = _tables()
    table = tables["record"]
    rows, total = repo.list_records_by_agent(
        agent_id=int(agent_id),
        page=max(1, int(page)),
        per_page=max(1, int(per_page)),
        sort="createdAt",
        order="DESC",
        q=keyword,
        table_name=table,
    )
    return {"rows": rows, "total": int(total)}


def get_doc_topk_messages(
    *,
    agent_id: int,
    message: str,
    messages: List[str],
    limit: int = 5,
    distance_metric: str = "euclidean",
    include_vector: bool = False,
) -> list[Dict[str, Any]]:
    """根据 Agent 关联文档循环检索相似文本块 Top-K

    参数：
    - agent_id：Agent 主键 ID（上层已确保存在）
    - message：输入消息文本
    - messages：查询短句列表 优先 使用，为空时 fallback 到 message
    - limit：返回条数上限（全局 Top-K）
    - distance_metric：距离度量方式（euclidean 或 cosine）
    - include_vector：是否返回向量

    返回：
    - 列表，每项包含 `chunk_id/doc_id/content/similarity_score`（当 `include_vector=True` 时包含 `embedding`）
    """
    logger = setup_logging(level="DEBUG", name="agentlz.rag_service", prefix="[RAG 服务]")
    logger.debug(f"进入 [get_doc_topk_messages] agent_id={agent_id} limit={limit}")

    if int(limit) <= 0:
        limit = 5
    doc_ids_grouped = doc_service.list_agent_related_document_ids_service(agent_id=int(agent_id))
    if not doc_ids_grouped:
        return []
    merged: list[Dict[str, Any]] = []
    for tid, did_list in doc_ids_grouped.items():
        # [{chunk_id, doc_id, content, created_at, similarity_score}]
        results = emb_service.search_similar_chunks_service(
            tenant_id=str(tid),
            message=message,
            messages=messages,
            doc_ids=[str(x) for x in did_list],
            distance_metric=distance_metric,
            limit=limit,
            include_vector=include_vector,
        )
        if results:
            merged.extend(results)

    merged.sort(key=lambda x: float(x.get("similarity_score", 1e9)))
    out = merged[:limit]
    for item in out:
        logger.debug(f"similarity_score={float(item.get("similarity_score", 1e9))}")
    logger.debug(f"完成 [get_doc_topk_messages] count={len(out)}")
    return out





def check_all_session_detail_by_record(*, record_id: int) -> List[Dict[str, Any]]:
    """检查记录关联的所有会话（输入/输出）

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


def check_session_for_rag(
    *, record_id: int, limit_input: int, limit_output: int
) -> List[Dict[str, Any]]:
    """检查记录关联会话（输入/输出）全部条数 ,但是可以限制前k条是原始会话,后面是zip压缩会话

    参数：
    - record_id：记录主键 ID（上层已确保存在）
    - limit_input：返回条数上限（从后往前数，0 表示不返回输入）
    - limit_output：返回条数上限（从后往前数，0 表示不返回输出）

    返回：
    - 列表，每项包含 `input/output/zip/count`（当 `limit_* > 0` 时包含对应值，否则为 None）
    """
    logger = setup_logging(level="DEBUG", name="agentlz.rag_service", prefix="[RAG 服务]")
    logger.debug(f"进入 [check_session_for_rag] record_id={record_id} li={limit_input} lo={limit_output}")
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
    try:
        rc = get_redis_client()
        rid = int(record_id)
        patterns = [f"record:*:{rid}:*"]
        keys: List[str] = []
        for p in patterns:
            try:
                keys.extend(list(rc.scan_iter(p)))
            except Exception:
                continue
        items: List[Dict[str, Any]] = []
        for k in keys:
            try:
                v = rc.get(k)
                if not v:
                    continue
                obj = json.loads(v)
                mi = obj.get("input")
                mo = obj.get("output")
                ca = obj.get("created_at")
                items.append({
                    "meta_input": json.dumps(mi, ensure_ascii=False) if not isinstance(mi, str) else mi,
                    "meta_output": json.dumps(mo, ensure_ascii=False) if not isinstance(mo, str) else mo,
                    "zip": "",
                    "created_at": ca,
                })
            except Exception:
                continue
        db_count = len(rows)
        redis_count = len(items)
        ttl = 3600
        if db_count > redis_count:
            for k in keys:
                try:
                    rc.expire(k, ttl)
                except Exception:
                    pass
            missing = db_count - redis_count
            if missing > 0:
                add_rows = rows[-missing:] if missing <= db_count else rows
                for r in add_rows:
                    try:
                        mi = r.get("meta_input")
                        mo = r.get("meta_output")
                        count = r.get("count") or 1
                        try:
                            inp = json.loads(mi) if isinstance(mi, str) else mi
                        except Exception:
                            inp = mi
                        try:
                            outp = json.loads(mo) if isinstance(mo, str) else mo
                        except Exception:
                            outp = mo
                        ca = r.get("created_at")
                        try:
                            ts = int(ca.timestamp())  # type: ignore
                        except Exception:
                            try:
                                ts = int(ca)  # type: ignore
                            except Exception:
                                ts = int(time.time())
                        sid = uuid.uuid4().hex[:8]
                        key = f"record:0:{rid}:{ts}:{sid}"
                        payload = {"input": inp, "output": outp, "created_at": ts}
                        try:
                            rc.set(key, json.dumps(payload, ensure_ascii=False), ex=ttl)
                        except Exception:
                            pass
                        items.append({
                            "meta_input": json.dumps(inp, ensure_ascii=False) if not isinstance(inp, str) else inp,
                            "meta_output": json.dumps(outp, ensure_ascii=False) if not isinstance(outp, str) else outp,
                            "zip": "",
                            "created_at": ts,
                            "count": count,
                        })
                    except Exception:
                        continue
        if items:
            items.sort(key=lambda x: int(x.get("created_at") or 0))
            rows.extend(items)
    except Exception:
        pass
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
    logger.debug(f"完成 [check_session_for_rag] 历史纪录检查到的数量:{len(out)}")
    return out



def get_sessions_by_record_paginated(
    *,
    agent_id: int,
    meta: Optional[Dict[str, Any]],
    record_id: int,
    page: int = 1,
    per_page: int = 10,
) -> Dict[str, Any]:
    """分页获取指定记录的会话列表（默认按创建时间倒序）

    参数：
    - agent_id：智能体主键 ID（上层已确保存在）
    - meta：记录元数据（可选）
    - record_id：记录主键 ID（默认 -1，记录id为0,没有历史纪录）
    - page：页码（默认 1）
    - per_page：每页数量（默认 10）

    返回：`{"rows": List[Dict[str, Any]], "total": int}`；
    每行包含：`id/count/input/output/zip/time`
    """
    logger = setup_logging(level="DEBUG", name="agentlz.rag_service", prefix="[RAG 服务]")
    logger.debug(f"进入 [get_sessions_by_record_paginated] agent_id={agent_id} record_id={record_id} page={page} per_page={per_page}")
    if int(record_id) <= 0:
        logger.error("错误 [get_sessions_by_record_paginated] record_id不合法")
        raise HTTPException(status_code=400, detail="record_id不合法")
    tables = _tables()
    rec_table = tables["record"]
    row = repo.get_record_by_id(record_id=int(record_id), table_name=rec_table)
    if not row:
        logger.error(f"错误 [get_sessions_by_record_paginated] Record ID 错误 record_id={record_id}")
        raise HTTPException(status_code=403, detail="Record ID 错误")
    elif row.get("agent_id") != int(agent_id) or row.get("meta") != meta:
        logger.error(f"错误 [get_sessions_by_record_paginated] Record不属于该Agent agent_id={agent_id} record_agent_id={row.get('agent_id')} meta_match={row.get('meta') == meta}")
        raise HTTPException(status_code=403, detail="Record不属于该Agent")
    ses_table = tables["session"]
    logger.debug(f"继续 [get_sessions_by_record_paginated] 开始分页查询 record_id={record_id} page={page} per_page={per_page}")
    rows, total = sess_repo.list_sessions_by_record_paginated(
        record_id=int(record_id),
        page=max(1, int(page)),
        per_page=max(1, int(per_page)),
        sort="createdAt",
        order="DESC",
        table_name=ses_table,
    )
    logger.debug(f"继续 [get_sessions_by_record_paginated] 查询到数量 rows={len(rows)} total={int(total)}")
    out_rows: List[Dict[str, Any]] = []
    logger.debug("继续 [get_sessions_by_record_paginated] 开始构建输出行")
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
        out_rows.append(
            {
                "id": int(r.get("id")),
                "count": int(r.get("count") or 0),
                "input": inp,
                "output": outp,
                "zip": r.get("zip"),
                "time": str(ca) if ca is not None else None,
            }
        )
    logger.debug(f"完成 [get_sessions_by_record_paginated] 返回数量:{len(out_rows)} 总数:{int(total)}")
    return {"rows": out_rows, "total": int(total)}


def agent_chat_get_rag(*, agent_id: int, message: str, record_id: int=-1, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """ RAG 检索 部分

    参数：
    - agent_id：智能体主键 ID（上层已确保存在）
    - message：用户输入消息
    - record_id：记录主键 ID（默认 -1，记录id为0,没有历史纪录）

    返回：
    - 列表 {"doc": doc_joined,// rag检索文档  str
     "history": his_joined, // 当前用户的历史问答记录 str
     "message": message, // 用户输入消息 str
     "messages": optimized_msgs // rag优化后的查询短句数组 str[]
     }
    """

    logger = setup_logging(level="DEBUG", name="agentlz.rag_service", prefix="[RAG 服务]")
    logger.debug(f"进入 [agent_chat_get_rag] agent_id={agent_id} record_id={record_id}")
    s = get_settings()
    tables = _tables()
    history: List[Dict[str, Any]] = []
    his_items: List[Tuple[str, str, str]] = []
    if int(record_id) > 0:
        # 1. 检查会话是否存在历史记录
        history = check_session_for_rag(record_id=int(record_id), limit_input=5, limit_output=5)
        his_items: List[Tuple[str, str, str]] = []
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
    else :
        logger.debug(f"没有历史记录")
        his_items=[]
        history=[]
    

    his_parts: List[str] = []
    for i, (inp, outp, z) in enumerate(his_items, start=1):
        his_parts.append(f"第{i}轮: human:{inp}, llm:{outp}, zip:{z}")
    his_joined = "; ".join(his_parts)

    # 没有历史记录时，创建新的记录
    if int(record_id) <= 0:
        logger.debug(f"创建新的记录")
        nm = str(message or "")
        created_row = repo.create_record(payload={"agent_id": int(agent_id), "name": nm, "meta": meta}, table_name=tables["record"])
        try:
            record_id = int(created_row.get("id"))
        except Exception:
            record_id = int(created_row.get("id") or -1)
    logger.debug(f"当前查询轮次属于的历史纪录: record_id={record_id}")
    # 2. 构建rag优化后的查询短句数组并进行rag检索
    try:
        rag: List[Dict[str, Any]] = []
        optimized_msgs: List[str] = []
        

        # message 不为空时，才进行rag检索
        if isinstance(message, str) and message.strip() != "":
            try:
                agent = get_rag_query_agent()
                combined_msg = (
                    f"历史上下文（仅用于改写指代，不抽取短句）：\n{his_joined}\n"
                    f"——分隔线——\n"
                    f"当前问题（仅从此处抽取）：\n{str(message)}\n"
                    f"输出要求：仅返回源自“当前问题”的短句"
                )
                rq_inp = RAGQueryInput(message=combined_msg, max_items=6)
                logger.debug(f"进入 agent 整合 messages")
                resp: Any = agent.invoke(rq_inp.model_dump())

                logger.debug(f"继续 [agent_chat_get_rag] agent理解message完毕, 输出了: resp={resp}")

                if isinstance(resp, dict) and resp.get("structured_response") is not None:
                    sr = resp["structured_response"]
                    try:
                        optimized_msgs = list(getattr(sr, "messages", []) or [])
                    except Exception:
                        optimized_msgs = []
                if not optimized_msgs:
                    try:
                        _q = RAGQueryInput(message=str(message), max_items=6)
                        _res = rag_build_queries(_q)
                        optimized_msgs = list(getattr(_res, "messages", []) or [])
                    except Exception:
                        optimized_msgs = []
            except Exception:
                logger.error(f"错误 [agent_chat_get_rag] agent理解message失败, message={message}")
                try:
                    combined_msg = (
                        f"历史上下文（仅用于改写指代，不抽取短句）：\n{his_joined}\n"
                        f"——分隔线——\n"
                        f"当前问题（仅从此处抽取）：\n{str(message)}\n"
                        f"输出要求：仅返回源自“当前问题”的短句"
                    )
                    _q = RAGQueryInput(message=str(message), max_items=6)
                    _res = rag_build_queries(_q)
                    optimized_msgs = list(getattr(_res, "messages", []) or [])
                except Exception:
                    optimized_msgs = []
            
            logger.debug(f"继续 [agent_chat_get_rag] 开始[get_doc_topk_messages] 优化后的messages={optimized_msgs}")
            rag = get_doc_topk_messages(agent_id=int(agent_id), message=message, messages=optimized_msgs)
            
        
        doc_texts: List[str] = []
        for x in rag:
            c = x.get("content")
            if c:
                doc_texts.append(str(c))
        doc_joined = "\n".join(doc_texts)

        out: Dict[str, Any] = {"doc": doc_joined, "history": his_joined, "message": message, "record_id": int(record_id)}
        out.update(RAGQueryOutput(messages=optimized_msgs or [str(message)]).model_dump())
        logger.debug(f"完成 [agent_chat_get_rag] record_id={record_id}")
        return out
    except Exception:
        logger.error(f"错误 [agent_chat_get_rag] record_id={record_id}")
        return {"message": str(message or ""), "doc": "", "history": "", "record_id": int(record_id)}

