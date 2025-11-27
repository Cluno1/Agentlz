from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy import text

from agentlz.core.database import get_mysql_engine

"""文档仓储（MySQL）

职责
- 提供文档的增删改查（CRUD）能力，严格基于多租户字段 `tenant_id` 做数据隔离
- 所有 SQL 使用参数化形式（sqlalchemy.text + 绑定参数），避免 SQL 注入
- 对排序字段进行白名单映射，防止外部传入任意列名参与 ORDER BY

表结构对齐（参见 `docs/deploy/sql/init_tenant.sql` 的 `document` 表）
- 主键：`id` varchar(64)
- 隔离：`tenant_id` varchar(64)
- 其他：`uploaded_by_user_id`、`status`、`upload_time`、`title`、`content` 等

性能与索引
- 常见列表查询包含：租户过滤、状态过滤、上传人过滤、标题模糊搜索
- 已建立索引：`tenant_id`、`uploaded_by_user_id`、(`tenant_id`,`status`)
- 大字段 `content` 进行 LIKE 模糊搜索会较慢，生产环境可考虑全文索引或外部检索

使用约定
- 更新接口不允许修改 `id` 和 `tenant_id`（主键与隔离维度）
- `upload_time` 默认由系统写入；如确需修改，需扩展白名单
"""


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

    # 组装 WHERE 条件与参数（强制带租户过滤）。
    # 安全：始终通过绑定参数传值，不拼接用户输入到 SQL 文本。
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
        SELECT id, tenant_id, uploaded_by_user_id, status, upload_time, title, content, type, tags, description, meta_https, save_https
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
        SELECT id, tenant_id, uploaded_by_user_id, status, upload_time, title, content, type, tags, description, meta_https, save_https
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
    
    # 构建动态SQL，支持可选字段
    columns = ["id", "tenant_id", "uploaded_by_user_id", "status", "upload_time", "title", "content","save_https"]
    values = [":id", ":tenant_id", ":uploaded_by_user_id", ":status", ":upload_time", ":title", ":content",":save_https"]
    
    # 添加可选字段
    if payload.get("document_type") is not None:
        columns.append("type")
        values.append(":type")
    
    if payload.get("tags") is not None:
        columns.append("tags")
        values.append(":tags")
    
    if payload.get("description") is not None:
        columns.append("description")
        values.append(":description")
    
    if payload.get("meta_https") is not None:
        columns.append("meta_https")
        values.append(":meta_https")
    
    sql = text(
        f"""
        INSERT INTO `{table_name}`
        ({', '.join(columns)})
        VALUES ({', '.join(values)})
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
        "save_https": payload.get("save_https"),
    }
    
    # 添加可选参数
    if "type" in columns:
        params["type"] = payload.get("document_type")
    if "tags" in columns:
        # 将标签列表转换为逗号分隔的字符串
        tags = payload.get("tags", [])
        if isinstance(tags, list):
            params["tags"] = ",".join(str(tag) for tag in tags)
        else:
            params["tags"] = str(tags)
    if "description" in columns:
        params["description"] = payload.get("description")
    if "meta_https" in columns:
        params["meta_https"] = payload.get("meta_https")

    engine = get_mysql_engine()
    with engine.begin() as conn:
        conn.execute(sql, params)
        # 读取并返回插入后的记录（与插入参数保持一致，避免脏读）
        ret = conn.execute(
            text(
                f"SELECT id, tenant_id, uploaded_by_user_id, status, upload_time, title, content, type, tags, description, meta_https FROM `{table_name}` WHERE id = :id AND tenant_id = :tenant_id"
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
    """
    更新文档，如果不存在返回 None
    
    参数：
    - `doc_id`: 文档ID
    - `payload`: 包含更新字段的字典
    - `tenant_id`: 租户ID
    - `table_name`: 文档表名
    
    返回：
    - 更新后的文档记录（字典格式），若文档不存在则返回 None
    
    异常：
    - `ValueError`: 若尝试更新 `tenant_id` 或 `id` 字段
    """

    allowed_cols = [
        "uploaded_by_user_id",
        "status",
        "title",
        "content",
        "type",
        "tags",
        "description",
        "meta_https",
        # 注：upload_time 通常由系统写入，不建议在普通更新中修改；如有需要可加入白名单
    ]

    sets = []
    params: Dict[str, Any] = {"id": doc_id, "tenant_id": tenant_id}
    for col in allowed_cols:
        if col in payload and payload[col] is not None:
            if col == "tags":
                # 将标签列表转换为逗号分隔的字符串
                tags = payload[col]
                if isinstance(tags, list):
                    params[col] = ",".join(str(tag) for tag in tags)
                else:
                    params[col] = str(tags)
            else:
                params[col] = payload[col]
            sets.append(f"{col} = :{col}")

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
                f"SELECT id, tenant_id, uploaded_by_user_id, status, upload_time, title, content, type, tags, description, meta_https, save_https FROM `{table_name}` WHERE id = :id AND tenant_id = :tenant_id"
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


def get_document_with_names_by_id(
    *,
    doc_id: str,
    tenant_id: str,
    table_name: str,
    user_table_name: str,
    tenant_table_name: str,
) -> Optional[Dict[str, Any]]:
    '''
    获取文档信息（按租户隔离），包含租户名称和上传用户名
    参数
    - doc_id: 文档ID
    - tenant_id: 租户ID
    - table_name: 文档表名
    - user_table_name: 用户表名
    - tenant_table_name: 租户表名
    返回
    - 文档信息（包含租户名称和上传用户名）
    '''
    sql = text(
        f"""
        SELECT 
            d.id, d.tenant_id, d.uploaded_by_user_id, d.status, d.upload_time, d.title, d.content, d.type, d.tags, d.description, d.meta_https, d.save_https,
            t.name AS tenant_name,
            u.full_name AS uploaded_by_user_name,
            u.username AS uploaded_by_user_username,
            u.avatar AS uploaded_by_user_avatar,
            u.email AS uploaded_by_user_email
        FROM `{table_name}` d
        LEFT JOIN `{tenant_table_name}` t ON d.tenant_id = t.id
        LEFT JOIN `{user_table_name}` u ON u.id = d.uploaded_by_user_id
        WHERE d.id = :id AND d.tenant_id = :tenant_id
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        row = conn.execute(sql, {"id": doc_id, "tenant_id": tenant_id}).mappings().first()
    return dict(row) if row else None


def list_documents_with_names(
    *,
    page: int,
    per_page: int,
    sort: str,
    order: str,
    q: Optional[str],
    tenant_id: str,
    table_name: str,
    user_table_name: str,
    tenant_table_name: str,
) -> Tuple[List[Dict[str, Any]], int]:
    '''
    获取文档列表（按租户隔离）
    参数
    - page: 页码
    - per_page: 每页数量
    - sort: 排序字段
    - order: 排序方向（ASC/DESC）
    - q: 搜索查询字符串
    - tenant_id: 租户ID
    - table_name: 文档表名
    - user_table_name: 用户表名
    - tenant_table_name: 租户表名
    返回
    - 文档列表（包含租户名称和上传用户名）
    - 总文档数
    '''
    order_dir = "ASC" if order.upper() == "ASC" else "DESC"
    sort_col = _sanitize_sort(sort)
    offset = (page - 1) * per_page

    where = ["d.tenant_id = :tenant_id"]
    params: Dict[str, Any] = {"tenant_id": tenant_id}
    if q:
        where.append("(d.title LIKE :q OR d.content LIKE :q)")
        params["q"] = f"%{q}%"
    where_sql = "WHERE " + " AND ".join(where)

    count_sql = text(f"SELECT COUNT(*) AS cnt FROM `{table_name}` d {where_sql}")
    list_sql = text(
        f"""
        SELECT 
            d.id, d.disabled, d.tenant_id, d.uploaded_by_user_id, d.status, d.upload_time, d.title, d.type, d.tags, d.description, d.meta_https, d.save_https,
            t.name AS tenant_name,
            u.full_name AS uploaded_by_user_name,
            u.username AS uploaded_by_user_username,
            u.avatar AS uploaded_by_user_avatar,
            u.email AS uploaded_by_user_email
        FROM `{table_name}` d
        LEFT JOIN `{tenant_table_name}` t ON d.tenant_id = t.id
        LEFT JOIN `{user_table_name}` u ON u.id = d.uploaded_by_user_id
        {where_sql}
        ORDER BY d.{sort_col} {order_dir}
        LIMIT :limit OFFSET :offset
        """
    )

    engine = get_mysql_engine()
    with engine.connect() as conn:
        total = conn.execute(count_sql, params).scalar() or 0
        rows = conn.execute(list_sql, {**params, "limit": per_page, "offset": offset}).mappings().all()
    return [dict(r) for r in rows], int(total)


def list_self_documents_with_names(
    *,
    page: int,
    per_page: int,
    sort: str,
    order: str,
    q: Optional[str],
    user_id: int,
    table_name: str,
    user_table_name: str,
    tenant_table_name: str,
) -> Tuple[List[Dict[str, Any]], int]:
    '''
    获取用户上传的文档列表（按租户隔离）
    参数
    - page: 页码
    - per_page: 每页数量
    - sort: 排序字段
    - order: 排序方向（ASC/DESC）
    - q: 搜索查询字符串
    - user_id: 用户ID
    - table_name: 文档表名
    - user_table_name: 用户表名
    - tenant_table_name: 租户表名
    返回
    - 文档列表（包含租户名称和上传用户名）
    - 总文档数
    '''
    order_dir = "ASC" if order.upper() == "ASC" else "DESC"
    sort_col = _sanitize_sort(sort)
    offset = (page - 1) * per_page

    where = ["d.tenant_id = :tenant_id", "d.uploaded_by_user_id = :user_id"]
    params: Dict[str, Any] = {"tenant_id": "default", "user_id": user_id}
    if q:
        where.append("(d.title LIKE :q OR d.content LIKE :q)")
        params["q"] = f"%{q}%"
    where_sql = "WHERE " + " AND ".join(where)

    count_sql = text(f"SELECT COUNT(*) AS cnt FROM `{table_name}` d {where_sql}")
    list_sql = text(
        f"""
        SELECT 
            d.id,d.disabled, d.tenant_id, d.uploaded_by_user_id, d.status, d.upload_time, d.title, d.type, d.tags, d.description, d.meta_https, d.save_https,
            t.name AS tenant_name,
            u.full_name AS uploaded_by_user_name,
            u.username AS uploaded_by_user_username,
            u.avatar AS uploaded_by_user_avatar,
            u.email AS uploaded_by_user_email
        FROM `{table_name}` d
        LEFT JOIN `{tenant_table_name}` t ON d.tenant_id = t.id
        LEFT JOIN `{user_table_name}` u ON u.id = d.uploaded_by_user_id
        {where_sql}
        ORDER BY d.{sort_col} {order_dir}
        LIMIT :limit OFFSET :offset
        """
    )

    engine = get_mysql_engine()
    with engine.connect() as conn:
        total = conn.execute(count_sql, params).scalar() or 0
        rows = conn.execute(list_sql, {**params, "limit": per_page, "offset": offset}).mappings().all()
    return [dict(r) for r in rows], int(total)


def list_tenant_documents_with_permission_with_names(
    *,
    page: int,
    per_page: int,
    sort: str,
    order: str,
    q: Optional[str],
    user_id: int,
    tenant_id: str,
    table_name: str,
    perm_table_name: str,
    user_table_name: str,
    tenant_table_name: str,
) -> Tuple[List[Dict[str, Any]], int]:
    order_dir = "ASC" if order.upper() == "ASC" else "DESC"
    sort_col = _sanitize_sort(sort)
    offset = (page - 1) * per_page

    where = ["d.tenant_id = :tenant_id"]
    params: Dict[str, Any] = {"tenant_id": tenant_id, "user_id": user_id}
    if q:
        where.append("(d.title LIKE :q OR d.content LIKE :q)")
        params["q"] = f"%{q}%"
    where_sql = "WHERE " + " AND ".join(where)

    count_sql = text(
        f"""
        SELECT COUNT(DISTINCT d.id) AS cnt
        FROM `{table_name}` d
        INNER JOIN `{perm_table_name}` udp ON d.id = udp.doc_id
        {where_sql} AND udp.user_id = :user_id AND udp.perm IN ('admin','read')
        """
    )

    list_sql = text(
        f"""
        SELECT DISTINCT 
            d.id, d.tenant_id, d.uploaded_by_user_id, d.status, d.upload_time, d.title, d.type, d.tags, d.description, d.meta_https, d.save_https,
            t.name AS tenant_name,
            u.full_name AS uploaded_by_user_name,
            u.username AS uploaded_by_user_username,
            u.avatar AS uploaded_by_user_avatar,
            u.email AS uploaded_by_user_email
        FROM `{table_name}` d
        INNER JOIN `{perm_table_name}` udp ON d.id = udp.doc_id
        LEFT JOIN `{tenant_table_name}` t ON d.tenant_id = t.id
        LEFT JOIN `{user_table_name}` u ON u.id = d.uploaded_by_user_id
        {where_sql} AND udp.user_id = :user_id AND udp.perm IN ('admin','read')
        ORDER BY d.{sort_col} {order_dir}
        LIMIT :limit OFFSET :offset
        """
    )

    engine = get_mysql_engine()
    with engine.connect() as conn:
        total = conn.execute(count_sql, params).scalar() or 0
        rows = conn.execute(list_sql, {**params, "limit": per_page, "offset": offset}).mappings().all()
    return [dict(r) for r in rows], int(total)