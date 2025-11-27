from __future__ import annotations
import logging
import time
from typing import Dict, Any
from agentlz.config.settings import get_settings
from agentlz.core.external_services import upload_to_cos

logger = logging.getLogger(__name__)

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
    """上传文档到COS , 返回后端标志的url"""
    return fastapi_prefix + upload_to_cos(document, filename, path)

def get_origin_url_from_save_https(url: str) -> str:
    """获取原始URL"""
    return get_cos_url(url.replace(fastapi_prefix, ""))

