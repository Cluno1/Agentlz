from __future__ import annotations
from typing import Any, Dict, List, Optional
from sqlalchemy import text
from agentlz.core.database import get_mysql_engine
from agentlz.config.settings import get_settings
from agentlz.core.logger import setup_logging
logger = setup_logging()


def _table_names():
    s = get_settings()
    return (
        getattr(s, "upload_task_table_name", "upload_task"),
        getattr(s, "upload_part_table_name", "upload_part"),
        getattr(s, "file_fingerprint_table_name", "file_fingerprint"),
    )


def create_upload_task(payload: Dict[str, Any]) -> Dict[str, Any]:
    task_table, _, _ = _table_names()
    sql = text(
        f"""
        INSERT INTO `{task_table}`
        (tenant_id, user_id, filename, size, content_type, file_type, chunk_size, chunk_count, cos_key, multipart_upload_id, status, scan_status, file_hash, title, description, tags, strategy, document_type, type, document_id, expires_at)
        VALUES
        (:tenant_id, :user_id, :filename, :size, :content_type, :file_type, :chunk_size, :chunk_count, :cos_key, :multipart_upload_id, :status, :scan_status, :file_hash, :title, :description, :tags, :strategy, :document_type, :type, :document_id, :expires_at)
        """
    )
    engine = get_mysql_engine()
    with engine.begin() as conn:
        res = conn.execute(sql, payload)
        task_id = res.lastrowid
        logger.debug(f"创建上传任务 task_id={task_id} filename={payload.get('filename')} cos_key={payload.get('cos_key')}")
        row = conn.execute(
            text(
                f"""
                SELECT * FROM `{task_table}` WHERE id = :id
                """
            ),
            {"id": task_id},
        ).mappings().first()
    return dict(row) if row else {}


def get_upload_task(*, task_id: int) -> Optional[Dict[str, Any]]:
    task_table, _, _ = _table_names()
    sql = text(f"SELECT * FROM `{task_table}` WHERE id = :id")
    engine = get_mysql_engine()
    with engine.connect() as conn:
        row = conn.execute(sql, {"id": task_id}).mappings().first()
    logger.debug(f"查询上传任务 task_id={task_id} 命中={row is not None}")
    return dict(row) if row else None


def update_upload_task(*, task_id: int, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    task_table, _, _ = _table_names()
    sets = []
    params: Dict[str, Any] = {"id": task_id}
    for k, v in payload.items():
        sets.append(f"{k} = :{k}")
        params[k] = v
    if not sets:
        return get_upload_task(task_id=task_id)
    sql = text(f"UPDATE `{task_table}` SET {', '.join(sets)} WHERE id = :id")
    engine = get_mysql_engine()
    with engine.begin() as conn:
        conn.execute(sql, params)
        row = conn.execute(
            text(f"SELECT * FROM `{task_table}` WHERE id = :id"),
            {"id": task_id},
        ).mappings().first()
    logger.debug(f"更新上传任务 task_id={task_id} 字段={list(payload.keys())}")
    return dict(row) if row else None


def list_upload_parts(*, task_id: int) -> List[Dict[str, Any]]:
    _, part_table, _ = _table_names()
    sql = text(
        f"""
        SELECT part_number, etag, part_hash, size, status, updated_at
        FROM `{part_table}`
        WHERE task_id = :task_id
        ORDER BY part_number ASC
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        rows = conn.execute(sql, {"task_id": task_id}).mappings().all()
    logger.debug(f"查询分片列表 task_id={task_id} 数量={len(rows)}")
    return [dict(r) for r in rows]


def get_uploaded_part_numbers(*, task_id: int) -> List[int]:
    _, part_table, _ = _table_names()
    sql = text(
        f"""
        SELECT part_number FROM `{part_table}` WHERE task_id = :task_id AND status = 'uploaded'
        ORDER BY part_number ASC
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        rows = conn.execute(sql, {"task_id": task_id}).fetchall()
    logger.debug(f"查询已上传分片编号 task_id={task_id} 数量={len(rows)}")
    return [int(r[0]) for r in rows]


def upsert_upload_part(*, task_id: int, part_number: int, payload: Dict[str, Any]) -> None:
    _, part_table, _ = _table_names()
    columns = ["task_id", "part_number", "etag", "part_hash", "size", "status"]
    params = {
        "task_id": task_id,
        "part_number": part_number,
        "etag": payload.get("etag"),
        "part_hash": payload.get("part_hash"),
        "size": payload.get("size"),
        "status": payload.get("status"),
    }
    sql = text(
        f"""
        INSERT INTO `{part_table}` ({', '.join(columns)})
        VALUES (:task_id, :part_number, :etag, :part_hash, :size, :status)
        ON DUPLICATE KEY UPDATE
        etag = VALUES(etag),
        part_hash = VALUES(part_hash),
        size = VALUES(size),
        status = VALUES(status)
        """
    )
    engine = get_mysql_engine()
    with engine.begin() as conn:
        conn.execute(sql, params)
    logger.debug(f"写入分片 task_id={task_id} part_number={part_number} status={payload.get('status')} size={payload.get('size')}")


def delete_upload_parts(*, task_id: int) -> None:
    _, part_table, _ = _table_names()
    sql = text(f"DELETE FROM `{part_table}` WHERE task_id = :task_id")
    engine = get_mysql_engine()
    with engine.begin() as conn:
        conn.execute(sql, {"task_id": task_id})
    logger.debug(f"删除分片记录 task_id={task_id}")


def get_fingerprint(*, tenant_id: str, file_hash: str, size: int) -> Optional[Dict[str, Any]]:
    _, _, fp_table = _table_names()
    sql = text(
        f"""
        SELECT * FROM `{fp_table}`
        WHERE tenant_id = :tenant_id AND file_hash = :file_hash AND size = :size
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        row = conn.execute(
            sql, {"tenant_id": tenant_id, "file_hash": file_hash, "size": size}
        ).mappings().first()
    logger.debug(f"查询文件指纹 tenant_id={tenant_id} md5={file_hash} size={size} 命中={row is not None}")
    return dict(row) if row else None


def upsert_fingerprint(payload: Dict[str, Any]) -> None:
    _, _, fp_table = _table_names()
    sql = text(
        f"""
        INSERT INTO `{fp_table}`
        (tenant_id, file_hash, size, cos_key, document_id, scan_status)
        VALUES
        (:tenant_id, :file_hash, :size, :cos_key, :document_id, :scan_status)
        ON DUPLICATE KEY UPDATE
        cos_key = VALUES(cos_key),
        document_id = VALUES(document_id),
        scan_status = VALUES(scan_status)
        """
    )
    engine = get_mysql_engine()
    with engine.begin() as conn:
        conn.execute(sql, payload)
    logger.debug(f"写入文件指纹 tenant_id={payload.get('tenant_id')} md5={payload.get('file_hash')} size={payload.get('size')} status={payload.get('scan_status')}")
