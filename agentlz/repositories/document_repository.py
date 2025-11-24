from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy import text

from agentlz.core.database import get_mysql_engine


# 排序字段白名单映射（外部字段名 -> 数据库列名）
# 目的：防止直接拼接用户输入到 SQL 导致注入；仅允许映射中出现的字段参与 ORDER BY
SORT_MAPPING = {
    "id": "id",
    "tenantId": "tenant_id",
    "uploadedBy": "uploaded_by_user_id",
    "uploadedByUserId": "uploaded_by_user_id",
    "status": "status",
    "uploadTime": "upload_time",
    "title": "title",
}


def _sanitize_sort(sort_field: str) -> str:
    # 过滤排序字段，仅允许预设映射中的键；否则默认按 id 排序
    return SORT_MAPPING.get(sort_field, "id")


def list_documents(
    *,
    page: int,
    per_page: int,
    sort: str,
    order: str,
    q: Optional[str],
    tenant_id: str,
    table_name: str,
) -> Tuple[List[Dict[str, Any]], int]:
    # 分页查询文档列表（按租户隔离），支持标题/内容模糊搜索
    """列表查询，返回行与总数"""

    order_dir = "ASC" if order.upper() == "ASC" else "DESC"
    sort_col = _sanitize_sort(sort)
    offset = (page - 1) * per_page

    # 组装 WHERE 条件与参数（强制带租户过滤）
    where = ["tenant_id = :tenant_id"]
    params: Dict[str, Any] = {"tenant_id": tenant_id}
    if q:
        # 对标题与内容做模糊匹配；注意 longtext LIKE 性能，生产可考虑全文索引
        where.append("(title LIKE :q OR content LIKE :q)")
        params["q"] = f"%{q}%"
    where_sql = "WHERE " + " AND ".join(where)

    count_sql = text(f"SELECT COUNT(*) AS cnt FROM `{table_name}` {where_sql}")
    list_sql = text(
        f"""
        SELECT id, tenant_id, uploaded_by_user_id, status, upload_time, title, content
        FROM `{table_name}`
        {where_sql}
        ORDER BY {sort_col} {order_dir}
        LIMIT :limit OFFSET :offset
        """
    )

    engine = get_mysql_engine()
    with engine.connect() as conn:
        total = conn.execute(count_sql, params).scalar() or 0
        rows = conn.execute(list_sql, {**params, "limit": per_page, "offset": offset}).mappings().all()
    return [dict(r) for r in rows], int(total)


def get_document_by_id(*, doc_id: str, tenant_id: str, table_name: str) -> Optional[Dict[str, Any]]:
    # 根据文档ID查询（租户隔离）
    sql = text(
        f"""
        SELECT id, tenant_id, uploaded_by_user_id, status, upload_time, title, content
        FROM `{table_name}` WHERE id = :id AND tenant_id = :tenant_id
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        row = conn.execute(sql, {"id": doc_id, "tenant_id": tenant_id}).mappings().first()
    return dict(row) if row else None


def create_document(
    *,
    payload: Dict[str, Any],
    tenant_id: str,
    table_name: str,
) -> Dict[str, Any]:
    # 创建文档并返回记录；若未提供 id 将自动生成 UUID
    """插入文档并返回插入后的记录"""

    # 生成 ID（若调用方未提供）
    doc_id = (payload.get("id") or __import__("uuid").uuid4().hex)[:64]
    now = datetime.now(timezone.utc)
    sql = text(
        f"""
        INSERT INTO `{table_name}`
        (id, tenant_id, uploaded_by_user_id, status, upload_time, title, content)
        VALUES (:id, :tenant_id, :uploaded_by_user_id, :status, :upload_time, :title, :content)
        """
    )

    params = {
        "id": doc_id,
        "tenant_id": tenant_id,
        "uploaded_by_user_id": payload.get("uploaded_by_user_id"),
        "status": payload.get("status"),
        "upload_time": now,
        "title": payload.get("title"),
        "content": payload.get("content"),
    }

    engine = get_mysql_engine()
    with engine.begin() as conn:
        conn.execute(sql, params)
        # 读取并返回插入后的记录
        ret = conn.execute(
            text(
                f"SELECT id, tenant_id, uploaded_by_user_id, status, upload_time, title, content FROM `{table_name}` WHERE id = :id AND tenant_id = :tenant_id"
            ),
            {"id": doc_id, "tenant_id": tenant_id},
        ).mappings().first()
        return dict(ret)


def update_document(
    *,
    doc_id: str,
    payload: Dict[str, Any],
    tenant_id: str,
    table_name: str,
) -> Optional[Dict[str, Any]]:
    # 更新文档信息（不可修改 tenant_id 与主键 id）
    """更新文档，如果不存在返回 None"""

    allowed_cols = [
        "uploaded_by_user_id",
        "status",
        "title",
        "content",
        # 注：upload_time 通常由系统写入，不建议在普通更新中修改；如有需要可加入白名单
    ]

    sets = []
    params: Dict[str, Any] = {"id": doc_id, "tenant_id": tenant_id}
    for col in allowed_cols:
        if col in payload and payload[col] is not None:
            sets.append(f"{col} = :{col}")
            params[col] = payload[col]

    if not sets:
        # 没有任何变更，直接返回当前记录
        return get_document_by_id(doc_id=doc_id, tenant_id=tenant_id, table_name=table_name)

    sql = text(
        f"UPDATE `{table_name}` SET " + ", ".join(sets) + " WHERE id = :id AND tenant_id = :tenant_id"
    )
    engine = get_mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(sql, params)
        if result.rowcount == 0:
            return None
        ret = conn.execute(
            text(
                f"SELECT id, tenant_id, uploaded_by_user_id, status, upload_time, title, content FROM `{table_name}` WHERE id = :id AND tenant_id = :tenant_id"
            ),
            {"id": doc_id, "tenant_id": tenant_id},
        ).mappings().first()
        return dict(ret) if ret else None


def delete_document(*, doc_id: str, tenant_id: str, table_name: str) -> bool:
    # 删除文档（按租户隔离）
    sql = text(f"DELETE FROM `{table_name}` WHERE id = :id AND tenant_id = :tenant_id")
    engine = get_mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(sql, {"id": doc_id, "tenant_id": tenant_id})
        return result.rowcount > 0