from __future__ import annotations
from typing import Any, Optional
from agentlz.core.external_services import get_redis_client


def cache_set(key: str, value: str, expire: int = 3600) -> bool:
    """设置缓存"""
    try:
        redis_client = get_redis_client()
        return redis_client.set(key, value, ex=expire)
    except Exception as e:
        # 记录日志但不抛出异常，避免影响主业务流程
        import logging
        logging.warning(f"Redis缓存设置失败: {e}")
        return False


def cache_get(key: str) -> Optional[str]:
    """获取缓存"""
    try:
        redis_client = get_redis_client()
        value = redis_client.get(key)
        return value if value else None
    except Exception as e:
        import logging
        logging.warning(f"Redis缓存获取失败: {e}")
        return None


def cache_delete(key: str) -> bool:
    """删除缓存"""
    try:
        redis_client = get_redis_client()
        return bool(redis_client.delete(key))
    except Exception as e:
        import logging
        logging.warning(f"Redis缓存删除失败: {e}")
        return False


def cache_exists(key: str) -> bool:
    """检查缓存是否存在"""
    try:
        redis_client = get_redis_client()
        return bool(redis_client.exists(key))
    except Exception as e:
        import logging
        logging.warning(f"Redis缓存检查失败: {e}")
        return False


def set_user_token(user_id: int, token: str, expire: int = 86400) -> bool:
    """设置用户token缓存（24小时默认）"""
    key = f"user_token:{user_id}"
    return cache_set(key, token, expire)


def get_user_token(user_id: int) -> Optional[str]:
    """获取用户token缓存"""
    key = f"user_token:{user_id}"
    return cache_get(key)


def delete_user_token(user_id: int) -> bool:
    """删除用户token缓存"""
    key = f"user_token:{user_id}"
    return cache_delete(key)


def set_document_cache(doc_id: int, content: str, expire: int = 7200) -> bool:
    """设置文档内容缓存（2小时默认）"""
    key = f"document:{doc_id}"
    return cache_set(key, content, expire)


def get_document_cache(doc_id: int) -> Optional[str]:
    """获取文档内容缓存"""
    key = f"document:{doc_id}"
    return cache_get(key)


def delete_document_cache(doc_id: int) -> bool:
    """删除文档内容缓存"""
    key = f"document:{doc_id}"
    return cache_delete(key)