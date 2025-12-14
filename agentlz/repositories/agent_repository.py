"""Agent 仓储（MySQL）

职责
- 提供 agent 的增删改查（CRUD）能力
- 所有 SQL 使用参数化形式（sqlalchemy.text + 绑定参数），避免 SQL 注入
- 对排序字段进行白名单映射，防止外部传入任意列名参与 ORDER BY

表结构对齐（参见 `docs/deploy/sql/init_mysql.sql` 的 `agent` 表）
- 主键：`id` bigint(20)
- 多租户：`tenant_id` 必填，所有查询与变更需要携带
- 索引：`idx_agent_disabled`、`idx_agent_created_at`、`fk_agent_created_by`

使用约定
- 更新接口不允许修改主键 `id` 与 `tenant_id`
- 删除/查询均校验 `tenant_id` 以确保租户隔离
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy import text

from agentlz.core.database import get_mysql_engine


# 排序字段白名单映射（外部字段名 -> 数据库列名）
SORT_MAPPING = {
    "id": "id",
    "name": "name",
    "description": "description",
    "apiName": "api_name",
    "apiKey": "api_key",
    "disabled": "disabled",
    "createdAt": "created_at",
    "updatedAt": "updated_at",
    "createdById": "created_by_id",
    "updatedById": "updated_by_id",
}


def _sanitize_sort(sort_field: str) -> str:
    # 过滤排序字段，未命中时默认按 id 排序
    return SORT_MAPPING.get(sort_field, "id")




def list_agents_agg(
    *,
    page: int,
    per_page: int,
    sort: str,
    order: str,
    q: Optional[str],
    tenant_id: str,
    agent_table_name: str,
    mcp_rel_table_name: str,
    mcp_table_name: str,
    agent_doc_table_name: str,
    doc_table_name: str,
) -> Tuple[List[Dict[str, Any]], int]:
    order_dir = "ASC" if order.upper() == "ASC" else "DESC"
    sort_col = _sanitize_sort(sort)
    offset = (page - 1) * per_page
    where = ["tenant_id = :tenant_id"]
    params: Dict[str, Any] = {"tenant_id": tenant_id}
    if q:
        where.append("(name LIKE :q)")
        params["q"] = f"%{q}%"
    where_sql = "WHERE " + " AND ".join(where)
    count_sql = text(f"SELECT COUNT(*) AS cnt FROM `{agent_table_name}` {where_sql}")
    list_sql = text(
        f"""
        SELECT 
            b.id, b.name, b.description, b.tenant_id, b.created_at, b.created_by_id, b.updated_at, b.updated_by_id, b.disabled,
            COALESCE(mcps.mcp_ids, '') AS mcp_ids,
            COALESCE(mcps.mcp_names, '') AS mcp_names,
            COALESCE(docs.doc_ids, '') AS doc_ids,
            COALESCE(docs.doc_titles, '') AS doc_titles
        FROM (
            SELECT id, name, description, tenant_id, created_at, created_by_id, updated_at, updated_by_id, disabled
            FROM `{agent_table_name}`
            {where_sql}
            ORDER BY {sort_col} {order_dir}
            LIMIT :limit OFFSET :offset
        ) AS b
        LEFT JOIN (
            SELECT am.agent_id,
                   GROUP_CONCAT(ma.id ORDER BY ma.id SEPARATOR ',') AS mcp_ids,
                   GROUP_CONCAT(ma.name ORDER BY ma.id SEPARATOR ',') AS mcp_names
            FROM `{mcp_rel_table_name}` am
            JOIN `{mcp_table_name}` ma ON ma.id = am.mcp_agent_id
            GROUP BY am.agent_id
        ) AS mcps ON mcps.agent_id = b.id
        LEFT JOIN (
            SELECT ad.agent_id,
                   GROUP_CONCAT(d.id ORDER BY d.id SEPARATOR ',') AS doc_ids,
                   GROUP_CONCAT(d.title ORDER BY d.id SEPARATOR ',') AS doc_titles
            FROM `{agent_doc_table_name}` ad
            JOIN `{doc_table_name}` d ON d.id = ad.document_id
            GROUP BY ad.agent_id
        ) AS docs ON docs.agent_id = b.id
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        total = conn.execute(count_sql, params).scalar() or 0
        rows = conn.execute(list_sql, {**params, "limit": per_page, "offset": offset}).mappings().all()
    return [dict(r) for r in rows], int(total)


def list_self_agents_agg(
    *,
    page: int,
    per_page: int,
    sort: str,
    order: str,
    q: Optional[str],
    user_id: int,
    agent_table_name: str,
    mcp_rel_table_name: str,
    mcp_table_name: str,
    agent_doc_table_name: str,
    doc_table_name: str,
) -> Tuple[List[Dict[str, Any]], int]:
    order_dir = "ASC" if order.upper() == "ASC" else "DESC"
    sort_col = sort if sort in {"id", "name", "description", "disabled", "created_at", "updated_at", "created_by_id", "updated_by_id"} else "id"
    offset = (page - 1) * per_page
    where = ["tenant_id = :tenant_id", "created_by_id = :uid"]
    params: Dict[str, Any] = {"tenant_id": "default", "uid": int(user_id)}
    if q:
        where.append("(name LIKE :q)")
        params["q"] = f"%{q}%"
    where_sql = "WHERE " + " AND ".join(where)
    count_sql = text(f"SELECT COUNT(*) AS cnt FROM `{agent_table_name}` {where_sql}")
    list_sql = text(
        f"""
        SELECT 
            b.id, b.name, b.description, b.tenant_id, b.created_at, b.created_by_id, b.updated_at, b.updated_by_id, b.disabled,
            COALESCE(mcps.mcp_ids, '') AS mcp_ids,
            COALESCE(mcps.mcp_names, '') AS mcp_names,
            COALESCE(docs.doc_ids, '') AS doc_ids,
            COALESCE(docs.doc_titles, '') AS doc_titles
        FROM (
            SELECT id, name, description, tenant_id, created_at, created_by_id, updated_at, updated_by_id, disabled
            FROM `{agent_table_name}`
            {where_sql}
            ORDER BY {sort_col} {order_dir}
            LIMIT :limit OFFSET :offset
        ) AS b
        LEFT JOIN (
            SELECT am.agent_id,
                   GROUP_CONCAT(ma.id ORDER BY ma.id SEPARATOR ',') AS mcp_ids,
                   GROUP_CONCAT(ma.name ORDER BY ma.id SEPARATOR ',') AS mcp_names
            FROM `{mcp_rel_table_name}` am
            JOIN `{mcp_table_name}` ma ON ma.id = am.mcp_agent_id
            GROUP BY am.agent_id
        ) AS mcps ON mcps.agent_id = b.id
        LEFT JOIN (
            SELECT ad.agent_id,
                   GROUP_CONCAT(d.id ORDER BY d.id SEPARATOR ',') AS doc_ids,
                   GROUP_CONCAT(d.title ORDER BY d.id SEPARATOR ',') AS doc_titles
            FROM `{agent_doc_table_name}` ad
            JOIN `{doc_table_name}` d ON d.id = ad.document_id
            GROUP BY ad.agent_id
        ) AS docs ON docs.agent_id = b.id
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        total = conn.execute(count_sql, params).scalar() or 0
        rows = conn.execute(list_sql, {**params, "limit": per_page, "offset": offset}).mappings().all()
    return [dict(r) for r in rows], int(total)


def get_agent_with_user_and_perm(
    *,
    agent_id: int,
    user_id: int,
    agent_table_name: str,
    user_table_name: str,
    perm_table_name: str,
) -> Optional[Dict[str, Any]]:
    sql = text(
        f"""
        SELECT 
            a.id, a.name, a.description, a.api_name, a.api_key, a.tenant_id, a.created_at, a.created_by_id, a.updated_at, a.updated_by_id, a.disabled,
            u.role AS user_role,
            u.tenant_id AS user_tenant_id,
            up.perm AS user_perm
        FROM `{agent_table_name}` a
        LEFT JOIN `{user_table_name}` u ON u.id = :uid
        LEFT JOIN `{perm_table_name}` up ON up.agent_id = a.id AND up.user_id = :uid
        WHERE a.id = :aid
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        row = conn.execute(sql, {"aid": int(agent_id), "uid": int(user_id)}).mappings().first()
    return dict(row) if row else None


def update_agent_no_read(
    *,
    agent_id: int,
    payload: Dict[str, Any],
    tenant_id: str,
    table_name: str,
) -> bool:
    allowed_cols = [
        "name",
        "description",
        "api_name",
        "api_key",
        "disabled",
        "created_by_id",
        "updated_by_id",
    ]
    sets: List[str] = []
    params: Dict[str, Any] = {"id": int(agent_id), "tenant_id": str(tenant_id)}
    for col in allowed_cols:
        if col in payload and payload[col] is not None:
            val = payload[col]
            if col == "disabled":
                val = int(bool(val))
            sets.append(f"{col} = :{col}")
            params[col] = val
    if not sets:
        return True
    sql = text(f"UPDATE `{table_name}` SET " + ", ".join(sets) + " WHERE id = :id AND tenant_id = :tenant_id")
    engine = get_mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(sql, params)
        return result.rowcount > 0


def get_agent_by_id(*, agent_id: int, tenant_id: str, table_name: str) -> Optional[Dict[str, Any]]:
    """
    按主键与租户查询单条 agent 记录。
    :param agent_id: 智能体ID
    :param tenant_id: 租户ID
    :param table_name: 表名
    :return: 智能体记录
    """
    # 精确匹配主键 + 租户实现隔离
    sql = text(
        f"""
        SELECT id, name, description, api_name, api_key, tenant_id, created_at, created_by_id, updated_at, updated_by_id, disabled
        FROM `{table_name}` WHERE id = :id AND tenant_id = :tenant_id
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        row = conn.execute(sql, {"id": agent_id, "tenant_id": tenant_id}).mappings().first()
    return dict(row) if row else None


def get_agent_by_id_any_tenant(*, agent_id: int, table_name: str) -> Optional[Dict[str, Any]]:
    sql = text(
        f"""
        SELECT id, name, description, api_name, api_key, tenant_id, created_at, created_by_id, updated_at, updated_by_id, disabled
        FROM `{table_name}` WHERE id = :id
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        row = conn.execute(sql, {"id": agent_id}).mappings().first()
    return dict(row) if row else None


def create_agent(
    *,
    payload: Dict[str, Any],
    tenant_id: str,
    table_name: str,
) -> Dict[str, Any]:
    """创建 agent 并回读插入后的完整记录。"""
    # 记录创建时间（UTC）
    now = datetime.now(timezone.utc)
    sql = text(
        f"""
        INSERT INTO `{table_name}`
        (name, description, api_name, api_key, tenant_id, created_at, created_by_id, disabled)
        VALUES (:name, :description, :api_name, :api_key, :tenant_id, :created_at, :created_by_id, :disabled)
        """
    )

    # 构造插入参数，disabled 规范化为 tinyint(1)
    params = {
        "name": payload.get("name"),
        "description": payload.get("description"),
        "api_name": payload.get("api_name"),
        "api_key": payload.get("api_key"),
        "tenant_id": tenant_id,
        "created_at": now,
        "created_by_id": payload.get("created_by_id"),
        "disabled": int(bool(payload.get("disabled", False))),
    }

    engine = get_mysql_engine()
    with engine.begin() as conn:
        # 事务执行插入并读取回写记录
        result = conn.execute(sql, params)
        new_id = result.lastrowid
        ret = conn.execute(
            text(
                f"SELECT id, name, description, api_name, api_key, tenant_id, created_at, created_by_id, updated_at, updated_by_id, disabled FROM `{table_name}` WHERE id = :id AND tenant_id = :tenant_id"
            ),
            {"id": new_id, "tenant_id": tenant_id},
        ).mappings().first()
        return dict(ret)


def update_agent(
    *,
    agent_id: int,
    payload: Dict[str, Any],
    tenant_id: str,
    table_name: str,
) -> Optional[Dict[str, Any]]:
    # 允许更新的列（不含主键/租户列）
    allowed_cols = [
        "name",
        "description",
        "api_name",
        "api_key",
        "disabled",
        "created_by_id",
        "updated_by_id",
    ]

    sets: List[str] = []
    # 绑定主键与租户，确保只更新当前租户的数据
    params: Dict[str, Any] = {"id": agent_id, "tenant_id": tenant_id}
    for col in allowed_cols:
        if col in payload and payload[col] is not None:
            val = payload[col]
            if col == "disabled":
                # 布尔值统一转为 tinyint(1)
                val = int(bool(val))
            sets.append(f"{col} = :{col}")
            params[col] = val

    if not sets:
        # 无任何变更时直接返回当前记录
        return get_agent_by_id(agent_id=agent_id, tenant_id=tenant_id, table_name=table_name)

    # 动态生成更新语句（参数化绑定）
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
                f"SELECT id, name, description, api_name, api_key, tenant_id, created_at, created_by_id, updated_at, updated_by_id, disabled FROM `{table_name}` WHERE id = :id AND tenant_id = :tenant_id"
            ),
            {"id": agent_id, "tenant_id": tenant_id},
        ).mappings().first()
        return dict(ret) if ret else None


def delete_agent(*, agent_id: int, tenant_id: str, table_name: str) -> bool:
    """按主键与租户删除 agent。"""
    # 删除时同样校验租户隔离
    sql = text(f"DELETE FROM `{table_name}` WHERE id = :id AND tenant_id = :tenant_id")
    engine = get_mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(sql, {"id": agent_id, "tenant_id": tenant_id})
        return result.rowcount > 0
