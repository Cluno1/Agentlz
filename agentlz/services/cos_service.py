from __future__ import annotations
"""
COS 服务封装（对象 URL 生成 + 简单上传 + Multipart 上传能力）。

本文件提供两类能力：
1) 兼容旧链路：后端直接 put_object（upload_document_to_cos）
2) 大文件链路：Multipart 上传编排（init -> presign part -> complete/abort）

阶段说明（Multipart 上传）：
- create_multipart_upload：创建一次 multipart 会话，返回 UploadId
- presign_upload_part：为某个 PartNumber 生成短期 PUT 直传 URL（前端直传 COS）
- complete_multipart_upload：按 parts(PartNumber/ETag) 完成合并
- abort_multipart_upload：中断并清理会话
- head_object：用于对账（大小/etag/元信息）

注意：
- Multipart 的 ETag 不是整文件 MD5，因此整文件 hash 需要单独计算（见 scan_service.scan_cos_object）
"""
import logging
from typing import Dict, Any, List
from agentlz.config.settings import get_settings
from agentlz.core.external_services import upload_to_cos, get_cos_client
from agentlz.core.logger import setup_logging

logger = setup_logging()

def get_cos_url(key: str) -> str:
    """获取COS对象的完整的URL"""
    
    s = get_settings()
    # 返回访问URL
    base_url = s.cos_base_url
    region = s.cos_region
    # 获取存储桶名称
    bucket = s.cos_bucket
    preHead=base_url.rstrip('/') if base_url else f"https://{bucket}.cos.{region}.myqcloud.com"
    # 构建完整的对象URL
    return f"{preHead}/{key.lstrip('/')}"

# fastapi 前缀
fastapi_prefix = "http://localhost:8000/v1/cos/"


def upload_document_to_cos(document: bytes, filename: str, path: str) -> str:
    """后端直传 COS（小文件链路使用），返回内部 save_https。

    阶段说明：
    - 由 core.external_services.upload_to_cos 完成 put_object
    - 返回值会被 document.save_https 存储为内部标识（带 /v1/cos/ 前缀）

    参数：
    - document: 文件二进制
    - filename: 文件名（会拼到 key 中）
    - path: COS 前缀路径（例如 quarantine/{tenant}/{user}/{date}）
    """
    logger.debug(f"直传COS filename={filename} path={path}")
    return fastapi_prefix + upload_to_cos(document, filename, path)

def get_origin_url_from_save_https(url: str) -> str:
    """将内部 save_https 转换为 COS 可访问的 HTTPS URL。"""
    return get_cos_url(url.replace(fastapi_prefix, ""))


def create_multipart_upload(key: str, content_type: str | None = None) -> str:
    """创建 multipart 上传会话，返回 UploadId。"""
    s = get_settings()
    client = get_cos_client()
    bucket = s.cos_bucket
    if not bucket:
        raise RuntimeError("COS存储桶配置缺失")
    logger.debug(f"创建Multipart key={key} content_type={content_type}")
    resp = client.create_multipart_upload(
        Bucket=bucket, Key=key, ContentType=content_type or "application/octet-stream"
    )
    return str(resp.get("UploadId") or "")


def presign_upload_part(
    key: str, upload_id: str, part_number: int, expires: int = 1800
) -> str:
    """生成指定分片的预签名 PUT URL，供前端直传 COS。"""
    s = get_settings()
    client = get_cos_client()
    bucket = s.cos_bucket
    if not bucket:
        raise RuntimeError("COS存储桶配置缺失")
    logger.debug(f"生成分片预签名URL key={key} upload_id={upload_id} part_number={part_number} expires={expires}")
    url = client.get_presigned_url(
        Bucket=bucket,
        Key=key,
        Method="PUT",
        Params={"UploadId": upload_id, "PartNumber": part_number},
        Expired=expires,
    )
    return str(url)


def complete_multipart_upload(
    key: str, upload_id: str, parts: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """完成 multipart 合并。

    参数 parts:
    - [{"PartNumber": 1, "ETag": "..."} ...]
    """
    s = get_settings()
    client = get_cos_client()
    bucket = s.cos_bucket
    if not bucket:
        raise RuntimeError("COS存储桶配置缺失")
    payload = {"Part": [{"PartNumber": p["PartNumber"], "ETag": p["ETag"]} for p in parts]}
    logger.debug(f"完成Multipart合并 key={key} upload_id={upload_id} parts={len(parts)}")
    resp = client.complete_multipart_upload(
        Bucket=bucket, Key=key, UploadId=upload_id, MultipartUpload=payload
    )
    return resp


def abort_multipart_upload(key: str, upload_id: str) -> None:
    """中断 multipart 上传会话。"""
    s = get_settings()
    client = get_cos_client()
    bucket = s.cos_bucket
    if not bucket:
        raise RuntimeError("COS存储桶配置缺失")
    logger.debug(f"中止Multipart key={key} upload_id={upload_id}")
    client.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload_id)


def head_object(key: str) -> Dict[str, Any]:
    """获取对象元信息，用于对账（大小、etag、metadata 等）。"""
    s = get_settings()
    client = get_cos_client()
    bucket = s.cos_bucket
    if not bucket:
        raise RuntimeError("COS存储桶配置缺失")
    logger.debug(f"查询对象元信息 key={key}")
    resp = client.head_object(Bucket=bucket, Key=key)
    return resp


def copy_object(src_key: str, dest_key: str) -> None:
    """COS 服务端拷贝对象（用于隔离区转正）。"""
    s = get_settings()
    client = get_cos_client()
    bucket = s.cos_bucket
    if not bucket:
        raise RuntimeError("COS存储桶配置缺失")
    source = {
        "Bucket": bucket,
        "Key": src_key,
        "Region": s.cos_region,
    }
    logger.debug(f"拷贝对象 src={src_key} dest={dest_key}")
    client.copy_object(Bucket=bucket, Key=dest_key, CopySource=source)


def delete_object(key: str) -> None:
    """删除对象（用于隔离区转正后清理原对象）。"""
    s = get_settings()
    client = get_cos_client()
    bucket = s.cos_bucket
    if not bucket:
        raise RuntimeError("COS存储桶配置缺失")
    logger.debug(f"删除对象 key={key}")
    client.delete_object(Bucket=bucket, Key=key)
