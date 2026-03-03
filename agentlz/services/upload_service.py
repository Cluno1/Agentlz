from __future__ import annotations
"""
分片上传编排服务（后端只做编排，分片由前端直传 COS）。

大文件链路（>=10MB）阶段说明：
1) init_upload：
   - 秒传判定：file_fingerprint 命中且 scan_status=passed 且不在 quarantine/ -> 直接 completed
   - 未命中：生成 quarantine cos_key，create_multipart_upload 得到 upload_id，落库 upload_task
2) get_part_url：
   - 校验任务归属后，为指定 part_number 返回 presigned PUT URL
3) complete_upload：
   - complete_multipart_upload 合并
   - 创建 document（status=pending_scan），并写 user_doc_permission
   - 更新 upload_task(status=completed, scan_status=pending) 并投递 doc_scan_tasks 扫描任务
4) scan_upload_task（见 scan_service）：
   - 扫描通过：隔离区转正 -> 更新 document -> 发布解析任务
   - 扫描失败：标记 scan_failed，禁止解析
"""
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import uuid
from fastapi import HTTPException
from agentlz.config.settings import get_settings
from agentlz.core.external_services import publish_to_rabbitmq
from agentlz.repositories import upload_repository as upload_repo
from agentlz.repositories import document_repository as doc_repo
from agentlz.repositories import user_doc_perm_repository as perm_repo
from agentlz.services.cos_service import (
    create_multipart_upload,
    presign_upload_part,
    complete_multipart_upload,
    abort_multipart_upload,
)
from agentlz.services.rag import document_service
from agentlz.core.logger import setup_logging
logger = setup_logging()


def _resolve_doc_tenant(type_value: str, tenant_id: str) -> str:
    """把外部的 type(self|tenant|system) 映射为 document.tenant_id。"""
    if type_value == "self":
        return "default"
    if type_value == "system":
        return "system"
    if type_value == "tenant":
        return tenant_id
    return "default"


def _build_quarantine_key(tenant_id: str, user_id: int, filename: str) -> str:
    """构造隔离区 COS key（quarantine 前缀）。"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    safe_name = filename.replace("/", "_").replace("\\", "_")
    return f"quarantine/{tenant_id}/{user_id}/{date_str}/{uuid.uuid4().hex[:16]}_{safe_name}"


def _chunk_base(file_type: str) -> int:
    """返回默认分片大小（前端会做动态档位调整，这里主要用于记录与提示）。"""
    mb = 1024 * 1024  # 1M 
    if file_type == "video":
        return 5 * mb
    return 2 * mb


def _chunk_min(file_type: str) -> int:
    """返回最小分片大小（用于粗略计算 chunk_count）。"""
    mb = 1024 * 1024
    if file_type == "video":
        return 2 * mb
    return 1 * mb


def init_upload(*, payload: Dict[str, Any], tenant_id: str, user_id: int) -> Dict[str, Any]:
    """初始化一个分片上传任务（或命中秒传直接完成）。

    入参 payload（来自 /v1/uploads/init）核心字段：
    - filename/size/content_type/file_type
    - file_hash（可选，整文件 MD5，用于秒传与完整性校验）
    - type(self|tenant|system) + title/description/tags/strategy/document_type（兼容 RAG 上传字段）

    返回：
    - 秒传命中：{"status":"completed","document_id":...,"final_url":...}
    - 新任务：{"task_id":...,"cos_key":...,"upload_id":...,"chunk_size":...,"chunk_count":...,"status":"uploading"}
    """
    file_hash = payload.get("file_hash")
    size = int(payload.get("size") or 0)
    doc_tenant_id = _resolve_doc_tenant(str(payload.get("type") or "self"), tenant_id)
    logger.debug(f"初始化上传 tenant_id={tenant_id} user_id={user_id} size={size} filename={payload.get('filename')} file_type={payload.get('file_type')} file_hash={file_hash}")
    if file_hash and size > 0:
        fp = upload_repo.get_fingerprint(
            tenant_id=doc_tenant_id, file_hash=str(file_hash), size=size
        )
        if fp and str(fp.get("scan_status")) == "passed" and "quarantine/" not in str(fp.get("cos_key") or ""):
            return {
                "status": "completed",
                "document_id": fp.get("document_id"),
                "final_url": document_service.build_save_https(str(fp.get("cos_key") or "")),
            }
    chunk_size = _chunk_base(str(payload.get("file_type") or "doc"))
    chunk_count = int((size + _chunk_min(str(payload.get("file_type") or "doc")) - 1) / _chunk_min(str(payload.get("file_type") or "doc")))
    filename = str(payload.get("filename") or "file")
    cos_key = _build_quarantine_key(doc_tenant_id, user_id, filename)
    upload_id = create_multipart_upload(cos_key, payload.get("content_type"))
    expires_at = datetime.now() + timedelta(days=1)
    row = upload_repo.create_upload_task(
        {
            "tenant_id": doc_tenant_id,
            "user_id": user_id,
            "filename": filename,
            "size": size,
            "content_type": payload.get("content_type"),
            "file_type": payload.get("file_type"),
            "chunk_size": chunk_size,
            "chunk_count": chunk_count,
            "cos_key": cos_key,
            "multipart_upload_id": upload_id,
            "status": "uploading",
            "scan_status": "pending",
            "file_hash": file_hash,
            "title": payload.get("title") or filename,
            "description": payload.get("description"),
            "tags": ",".join(payload.get("tags") or []) if payload.get("tags") else None,
            "strategy": (
                ",".join([str(x) for x in payload.get("strategy") or []])
                if payload.get("strategy")
                else None
            ),
            "document_type": payload.get("document_type"),
            "type": payload.get("type") or "self",
            "document_id": None,
            "expires_at": expires_at,
        }
    )
    logger.debug(f"初始化上传 创建任务成功 task_id={row.get('id')} cos_key={row.get('cos_key')} upload_id={row.get('multipart_upload_id')}")
    return {
        "task_id": row.get("id"),
        "cos_key": row.get("cos_key"),
        "upload_id": row.get("multipart_upload_id"),
        "chunk_size": row.get("chunk_size"),
        "chunk_count": row.get("chunk_count"),
        "status": row.get("status"),
    }


def get_upload_status(*, task_id: int, tenant_id: str, user_id: int) -> Dict[str, Any]:
    """查询上传任务状态（用于断点续传对齐 uploaded_parts）。"""
    task = upload_repo.get_upload_task(task_id=task_id)
    if not task:        
        raise HTTPException(status_code=404, detail="上传任务不存在")
    if str(task.get("tenant_id")) != tenant_id or int(task.get("user_id") or 0) != int(user_id):
        raise HTTPException(status_code=403, detail="无权限访问上传任务")
    parts = upload_repo.get_uploaded_part_numbers(task_id=task_id)
    final_url = None
    if str(task.get("scan_status")) == "passed":
        final_url = document_service.build_save_https(str(task.get("cos_key") or ""))
    logger.debug(f"查询上传状态 task_id={task_id} status={task.get('status')} scan_status={task.get('scan_status')} uploaded_parts={len(parts)}")
    return {
        "status": task.get("status"),
        "scan_status": task.get("scan_status"),
        "chunk_size": task.get("chunk_size"),
        "chunk_count": task.get("chunk_count"),
        "uploaded_parts": parts,
        "final_url": final_url,
        "document_id": task.get("document_id"),
    }


def get_part_url(
    *, task_id: int, tenant_id: str, user_id: int, part_number: int, part_size: int, part_hash: Optional[str]
) -> Dict[str, Any]:
    """获取指定分片的预签名直传 URL（PUT）。"""
    task = upload_repo.get_upload_task(task_id=task_id)
    if not task:
        raise HTTPException(status_code=404, detail="上传任务不存在")
    if str(task.get("tenant_id")) != tenant_id or int(task.get("user_id") or 0) != int(user_id):
        raise HTTPException(status_code=403, detail="无权限访问上传任务")
    if part_number <= 0:
        raise HTTPException(status_code=400, detail="分片编号无效")
    logger.debug(f"申请分片URL task_id={task_id} part_number={part_number} part_size={part_size}")
    url = presign_upload_part(
        key=str(task.get("cos_key")),
        upload_id=str(task.get("multipart_upload_id")),
        part_number=part_number,
        expires=1800,
    )
    return {"url": url, "method": "PUT", "required_headers": {}}


def _create_document_for_upload_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """在 multipart complete 后创建一条 document 记录（先 pending_scan，不触发解析）。"""
    table_name = document_service.get_document_table_name()
    tenant_id = str(task.get("tenant_id") or "default")
    save_https = document_service.build_save_https(str(task.get("cos_key") or ""))
    logger.debug(f"为上传任务创建文档 tenant_id={tenant_id} save_https={save_https}")
    payload = {
        "document_type": str(task.get("document_type") or "txt"),
        "title": task.get("title") or task.get("filename"),
        "tags": (
            [x for x in str(task.get("tags") or "").split(",") if x]
            if task.get("tags")
            else []
        ),
        "description": task.get("description") or "",
        "meta_https": "",
        "type": task.get("type") or "self",
        "tenant_id": tenant_id,
        "uploaded_by_user_id": int(task.get("user_id") or 0),
        "status": "pending_scan",
        "content": "",
        "save_https": save_https,
    }
    row = doc_repo.create_document(payload=payload, tenant_id=tenant_id, table_name=table_name)
    s = get_settings()
    perm_table = getattr(s, "user_doc_permission_table_name", "user_doc_permission")
    try:
        perm_repo.create_user_doc_perm(
            payload={"user_id": int(task.get("user_id") or 0), "doc_id": row.get("id"), "perm": "admin"},
            table_name=perm_table,
        )
    except Exception:
        pass
    logger.debug(f"创建文档成功 doc_id={row.get('id')}")
    return row


def complete_upload(
    *, task_id: int, tenant_id: str, user_id: int, parts: List[Dict[str, Any]], file_hash: Optional[str]
) -> Dict[str, Any]:
    """完成 multipart 合并，并触发扫描任务。

    阶段说明：
    - 校验任务归属
    - complete_multipart_upload 合并对象
    - 创建 document（pending_scan）
    - 更新 upload_task 并 publish doc_scan_tasks（由 mq_service 消费后调用 scan_service.scan_upload_task）
    """
    task = upload_repo.get_upload_task(task_id=task_id)
    if not task:
        raise HTTPException(status_code=404, detail="上传任务不存在")
    if str(task.get("tenant_id")) != tenant_id or int(task.get("user_id") or 0) != int(user_id):
        raise HTTPException(status_code=403, detail="无权限访问上传任务")
    if not parts:
        raise HTTPException(status_code=400, detail="分片列表为空")
    logger.debug(f"完成合并 task_id={task_id} parts={len(parts)}")
    sorted_parts = sorted(parts, key=lambda p: int(p["part_number"]))
    complete_parts = []
    for p in sorted_parts:
        complete_parts.append({"PartNumber": int(p["part_number"]), "ETag": str(p["etag"])})
        upload_repo.upsert_upload_part(
            task_id=task_id,
            part_number=int(p["part_number"]),
            payload={
                "etag": str(p["etag"]),
                "part_hash": p.get("part_hash"),
                "size": int(p.get("size") or 0),
                "status": "uploaded",
            },
        )
    complete_multipart_upload(
        key=str(task.get("cos_key")),
        upload_id=str(task.get("multipart_upload_id")),
        parts=complete_parts,
    )
    doc_row = _create_document_for_upload_task(task)
    upload_repo.update_upload_task(
        task_id=task_id,
        payload={"status": "completed", "document_id": doc_row.get("id"), "file_hash": file_hash or task.get("file_hash")},
    )
    publish_to_rabbitmq("doc_scan_tasks", {"task_id": task_id}, durable=True)
    logger.debug(f"已投递扫描任务 task_id={task_id} doc_id={doc_row.get('id')}")
    return {
        "status": "completed",
        "document_id": doc_row.get("id"),
        "final_url": None,
    }


def abort_upload(*, task_id: int, tenant_id: str, user_id: int) -> Dict[str, Any]:
    """终止 multipart 上传任务并清理分片记录。"""
    task = upload_repo.get_upload_task(task_id=task_id)
    if not task:
        raise HTTPException(status_code=404, detail="上传任务不存在")
    if str(task.get("tenant_id")) != tenant_id or int(task.get("user_id") or 0) != int(user_id):
        raise HTTPException(status_code=403, detail="无权限访问上传任务")
    logger.debug(f"终止上传 task_id={task_id}")
    abort_multipart_upload(key=str(task.get("cos_key")), upload_id=str(task.get("multipart_upload_id")))
    upload_repo.update_upload_task(task_id=task_id, payload={"status": "aborted"})
    upload_repo.delete_upload_parts(task_id=task_id)
    return {"status": "aborted"}
