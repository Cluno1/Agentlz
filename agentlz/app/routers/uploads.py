from __future__ import annotations
from typing import Dict, Any
from fastapi import APIRouter, Depends, Request
from agentlz.app.deps.auth_deps import require_auth, require_tenant_id
from agentlz.schemas.responses import Result
from agentlz.schemas.uploads import (
    UploadInitRequest,
    UploadInitResponse,
    UploadStatusResponse,
    UploadPartUrlRequest,
    UploadPartUrlResponse,
    UploadCompleteRequest,
    UploadCompleteResponse,
)
from agentlz.services import upload_service
from agentlz.core.logger import setup_logging

router = APIRouter(prefix="/v1/uploads", tags=["uploads"])
logger = setup_logging()


@router.post("/init", response_model=Result)
def init_upload(payload: UploadInitRequest, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    """
    初始化分片上传任务接口。

    主要职责：
    - 根据当前登录用户的信息（tenant_id、user_id）和前端上报的文件元数据（文件名、大小、类型、指纹等）
      调用 upload_service.init_upload 创建或复用一个上传任务。
    - 若命中秒传（file_fingerprint 已存在且扫描通过），直接返回已完成状态；
    - 否则在隔离区生成 cos_key 和 multipart UploadId，并在数据库中落一条 upload_task 记录，供后续分片上传使用。

    参数说明：
    - payload: UploadInitRequest，请求体，包含 filename/size/content_type/file_type/file_hash/type/title/description/tags/strategy 等业务字段；
    - request: FastAPI Request，用于提取租户信息；
    - claims: 登录用户的 JWT claims，通过 require_auth 注入，包含 sub（user_id）等。

    返回值：
    - Result 包装的 UploadInitResponse：
      - 秒传命中时：status=completed，返回 document_id / final_url；
      - 正常初始化时：返回 task_id / cos_key / upload_id / chunk_size / chunk_count / status=uploading。
    """
    tenant_id = require_tenant_id(request)
    user_id = int(claims.get("sub") or 0)
    logger.debug(f"上传初始化 请求 tenant_id={tenant_id} user_id={user_id} size={payload.size} filename={payload.filename} file_type={payload.file_type}")
    data = upload_service.init_upload(payload=payload.model_dump(), tenant_id=tenant_id, user_id=user_id)
    logger.debug(f"上传初始化 响应 status={data.get('status')} task_id={data.get('task_id')} cos_key={data.get('cos_key')}")
    return Result.ok(data=UploadInitResponse(**data))


@router.get("/{task_id}", response_model=Result)
def get_upload(task_id: int, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    """
    查询分片上传任务状态接口。

    主要职责：
    - 根据 task_id 查询对应的 upload_task 记录；
    - 校验当前用户对该任务是否有访问权限（tenant_id + user_id）；
    - 返回上传任务当前的总体状态与已上传分片列表，用于前端断点续传对齐。

    参数说明：
    - task_id: 上传任务主键 ID，由 /init 接口返回；
    - request: 用于解析当前请求的 tenant_id；
    - claims: 当前登录用户信息，确保只能查看自己的任务。

    返回值：
    - Result 包装的 UploadStatusResponse：
      - status: 上传任务状态（uploading/completed/failed/aborted 等）；
      - scan_status: 扫描状态（pending/passed/failed）；
      - chunk_size / chunk_count: 分片大小与总分片数；
      - uploaded_parts: 后端已确认上传成功的分片编号列表；
      - final_url / document_id: 在任务完成且扫描通过后，可能包含文档访问地址与文档 ID。
    """
    tenant_id = require_tenant_id(request)
    user_id = int(claims.get("sub") or 0)
    logger.debug(f"查询上传任务 请求 task_id={task_id} tenant_id={tenant_id} user_id={user_id}")
    data = upload_service.get_upload_status(task_id=task_id, tenant_id=tenant_id, user_id=user_id)
    logger.debug(f"查询上传任务 响应 status={data.get('status')} scan_status={data.get('scan_status')} uploaded_parts={len(data.get('uploaded_parts') or [])}")
    return Result.ok(data=UploadStatusResponse(**data))


@router.post("/{task_id}/part-url", response_model=Result)
def get_part_url(task_id: int, payload: UploadPartUrlRequest, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    """
    申请单个分片的预签名上传 URL 接口。

    主要职责：
    - 校验当前用户对 task_id 对应任务的权限；
    - 根据 part_number / part_size（以及可选的 part_hash）调用 upload_service.get_part_url，
      生成该分片的 COS 直传预签名 URL；
    - 将 URL 和必要的请求头信息返回给前端，前端据此执行 PUT 上传。

    参数说明：
    - task_id: 上传任务主键 ID；
    - payload: UploadPartUrlRequest，包含 part_number、part_size、part_hash 等字段；
    - request: 用于获取 tenant_id；
    - claims: 当前登录用户信息，用于任务归属校验。

    返回值：
    - Result 包装的 UploadPartUrlResponse：
      - url: 该分片对应的预签名 PUT 地址（直连 COS，不经过业务后端）；
      - required_headers: 前端在 PUT 时需要附带的请求头（如 Content-Type 等）。
    """
    tenant_id = require_tenant_id(request)
    user_id = int(claims.get("sub") or 0)
    logger.debug(f"申请分片URL 请求 task_id={task_id} tenant_id={tenant_id} user_id={user_id} part_number={payload.part_number} part_size={payload.part_size}")
    data = upload_service.get_part_url(
        task_id=task_id,
        tenant_id=tenant_id,
        user_id=user_id,
        part_number=payload.part_number,
        part_size=payload.part_size,
        part_hash=payload.part_hash,
    )
    logger.debug(f"申请分片URL 响应 url_len={len(data.get('url') or '')}")
    return Result.ok(data=UploadPartUrlResponse(**data))


@router.post("/{task_id}/complete", response_model=Result)
def complete_upload(task_id: int, payload: UploadCompleteRequest, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    """
    完成分片上传合并接口。

    主要职责：
    - 前端在所有分片上传完成后，将每个分片的 part_number 与 etag（以及可选 part_hash）上报；
    - 校验任务归属后调用 upload_service.complete_upload：
      - 调用 COS 的 complete_multipart_upload 合并所有分片；
      - 更新 upload_task 状态（status=completed，scan_status=pending）；
      - 创建或更新 document 记录（save_https 指向隔离区对象）；
      - 投递扫描任务（例如 doc_scan_tasks）。

    参数说明：
    - task_id: 上传任务主键 ID；
    - payload: UploadCompleteRequest，包含 parts 列表与可选的整文件 file_hash；
    - request / claims: 用于租户与用户鉴权。

    返回值：
    - Result 包装的 UploadCompleteResponse：
      - status: completed / waiting_scan 等；
      - document_id: 创建的文档 ID；
      - final_url: 若后端已知可用访问地址则返回，否则通常为 None（等待扫描转正后才可用）。
    """
    tenant_id = require_tenant_id(request)
    user_id = int(claims.get("sub") or 0)
    logger.debug(f"完成上传合并 请求 task_id={task_id} tenant_id={tenant_id} user_id={user_id} parts={len(payload.parts)}")
    data = upload_service.complete_upload(
        task_id=task_id,
        tenant_id=tenant_id,
        user_id=user_id,
        parts=[p.model_dump() for p in payload.parts],
        file_hash=payload.file_hash,
    )
    logger.debug(f"完成上传合并 响应 status={data.get('status')} document_id={data.get('document_id')}")
    return Result.ok(data=UploadCompleteResponse(**data))


@router.post("/{task_id}/abort", response_model=Result)
def abort_upload(task_id: int, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    """
    取消分片上传任务接口。

    主要职责：
    - 允许用户在上传过程中主动取消当前任务；
    - 校验任务归属后调用 upload_service.abort_upload：
      - 调用 COS 的 abort_multipart_upload 释放服务端 UploadId 会话；
      - 将 upload_task 状态标记为 aborted；
      - 清理已记录的分片信息。

    参数说明：
    - task_id: 上传任务主键 ID；
    - request / claims: 用于校验 tenant_id 与 user_id。

    返回值：
    - Result 包装一个简单的状态字典，例如 {"status": "aborted"}，表示取消成功。
    """
    tenant_id = require_tenant_id(request)
    user_id = int(claims.get("sub") or 0)
    logger.debug(f"取消上传 请求 task_id={task_id} tenant_id={tenant_id} user_id={user_id}")
    data = upload_service.abort_upload(task_id=task_id, tenant_id=tenant_id, user_id=user_id)
    return Result.ok(data=data)
