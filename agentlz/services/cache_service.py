from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
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


def _chat_lock_key(record_id: int) -> str:
    """生成 record_id 对应的 Redis 锁 key。"""
    return f"chat:lock:record:{int(record_id)}"


def acquire_chat_lock(*, record_id: int, token: str, ttl_ms: int = 30000) -> bool:
    """获取对 record_id 的互斥锁（用于串行化同一记录的并发请求）。

    实现：
    - 使用 Redis `SET key value NX PX ttl_ms`，其中 value=token
    - 获取成功返回 True；失败（已被占用/异常）返回 False
    """
    try:
        rc = get_redis_client()
        return bool(rc.set(_chat_lock_key(int(record_id)), str(token), nx=True, px=int(ttl_ms)))
    except Exception:
        return False


def release_chat_lock(*, record_id: int, token: str) -> bool:
    """释放 record_id 对应的互斥锁（仅在 token 匹配时删除）。

    说明：
    - 释放锁使用 Lua 先校验 token，避免误删其他请求持有的锁
    """
    lua = """
    if redis.call('GET', KEYS[1]) == ARGV[1] then
        return redis.call('DEL', KEYS[1])
    else
        return 0
    end
    """
    try:
        rc = get_redis_client()
        return bool(rc.eval(lua, 1, _chat_lock_key(int(record_id)), str(token)))
    except Exception:
        return False


def chat_history_keys(*, record_id: int) -> Tuple[str, str, str]:
    """返回对话历史在 Redis 的 keys（三件套：ids/list + map/hash + meta/hash）。"""
    rid = int(record_id)
    return (
        f"chat:history:{rid}:ids",
        f"chat:history:{rid}:map",
        f"chat:history:{rid}:meta",
    )


def chat_history_get(*, record_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """读取某个 record_id 最近 N 条会话历史（按旧→新顺序）。

    行为：
    - 先从 ids(list) 取出最近 N 个 session_id，再从 map(hash) 批量 HMGET
    - 若出现缺项（HMGET 含 None），认为缓存不完整，返回空列表，交由上层回退 MySQL
    """
    ids_key, map_key, _ = chat_history_keys(record_id=int(record_id))
    try:
        rc = get_redis_client()
        ids = rc.lrange(ids_key, -int(limit), -1)
        if not ids:
            return []
        values = rc.hmget(map_key, ids)
        if not values or any(v is None for v in values):
            return []
        out: List[Dict[str, Any]] = []
        for raw in values or []:
            if not raw:
                continue
            try:
                import json
                obj = json.loads(raw)
                if isinstance(obj, dict):
                    out.append(obj)
            except Exception:
                continue
        return out
    except Exception:
        return []


def chat_history_overwrite(*, record_id: int, items: List[Dict[str, Any]], ttl: int = 3600, limit: int = 50) -> bool:
    """用给定 items 覆盖该 record_id 的历史缓存，并自动裁剪到最近 N 条。"""
    ids_key, map_key, meta_key = chat_history_keys(record_id=int(record_id))
    try:
        import json
        rc = get_redis_client()
        trimmed = list(items[-int(limit):]) if items else []
        pipe = rc.pipeline()
        pipe.delete(ids_key)
        pipe.delete(map_key)
        pipe.delete(meta_key)
        if trimmed:
            ids: List[str] = []
            mapping: Dict[str, str] = {}
            for it in trimmed:
                sid = str(it.get("session_id") or it.get("id") or "")
                if not sid:
                    continue
                ids.append(sid)
                mapping[sid] = json.dumps(it, ensure_ascii=False)
            if ids:
                pipe.rpush(ids_key, *ids)
            if mapping:
                pipe.hset(map_key, mapping=mapping)
        pipe.expire(ids_key, int(ttl))
        pipe.expire(map_key, int(ttl))
        pipe.expire(meta_key, int(ttl))
        pipe.execute()
        return True
    except Exception:
        return False


def chat_history_append(*, record_id: int, session_id: int, item: Dict[str, Any], ttl: int = 3600, limit: int = 50) -> bool:
    """向 record_id 的历史缓存追加 1 条，并保证最多保留 N 条。

    实现：
    - 用 Lua 脚本原子执行：RPUSH(ids) + HSET(map) + LTRIM + HDEL(被裁剪的旧 id) + EXPIRE
    - 避免并发下 list/hash 不一致
    """
    ids_key, map_key, meta_key = chat_history_keys(record_id=int(record_id))
    lua = """
    local ids_key = KEYS[1]
    local map_key = KEYS[2]
    local meta_key = KEYS[3]
    local sid = ARGV[1]
    local json_value = ARGV[2]
    local limit = tonumber(ARGV[3])
    local ttl = tonumber(ARGV[4])

    local new_len = redis.call('RPUSH', ids_key, sid)
    redis.call('HSET', map_key, sid, json_value)
    if new_len > limit then
        local trim_count = new_len - limit
        local old_ids = redis.call('LRANGE', ids_key, 0, trim_count - 1)
        redis.call('LTRIM', ids_key, trim_count, -1)
        if #old_ids > 0 then
            redis.call('HDEL', map_key, unpack(old_ids))
        end
    end
    redis.call('EXPIRE', ids_key, ttl)
    redis.call('EXPIRE', map_key, ttl)
    redis.call('EXPIRE', meta_key, ttl)
    return 1
    """
    try:
        import json
        rc = get_redis_client()
        sid = str(int(session_id))
        value = json.dumps(item, ensure_ascii=False)
        return bool(rc.eval(lua, 3, ids_key, map_key, meta_key, sid, value, int(limit), int(ttl)))
    except Exception:
        return False


def chat_history_set_item(*, record_id: int, session_id: int, item: Dict[str, Any], ttl: int = 3600) -> bool:
    """更新某个 session_id 在历史缓存中的条目（常用于补齐 zip/状态），并刷新 TTL。"""
    ids_key, map_key, meta_key = chat_history_keys(record_id=int(record_id))
    try:
        import json
        rc = get_redis_client()
        pipe = rc.pipeline()
        pipe.hset(map_key, str(int(session_id)), json.dumps(item, ensure_ascii=False))
        pipe.expire(ids_key, int(ttl))
        pipe.expire(map_key, int(ttl))
        pipe.expire(meta_key, int(ttl))
        pipe.execute()
        return True
    except Exception:
        return False
