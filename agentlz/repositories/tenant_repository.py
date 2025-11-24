from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy import text

from agentlz.core.database import get_mysql_engine

"""租户仓储（MySQL）

职责
- 提供租户的增删改查（CRUD）能力
- 所有 SQL 使用参数化形式（sqlalchemy.text + 绑定参数），避免 SQL 注入
- 对排序字段进行白名单映射，防止外部传入任意列名参与 ORDER BY

表结构对齐（参见 `docs/deploy/sql/init_tenant.sql` 的 `tenant` 表）
- 主键：`id` varchar(64)
- 基本信息：`name`、`disabled`、`created_at`、`updated_at`

性能与索引
- 已建立索引：`name` 唯一索引、`disabled` 状态索引
- 常见查询包含：名称精确查找、状态筛选、分页排序

使用约定
- 更新接口不允许修改主键 `id`
"""


# 排序字段白名单映射（外部字段名 -> 数据库列名）
SORT_MAPPING = {
    "id": "id",
    "name": "name",
    "disabled": "disabled",
    "createdAt": "created_at",
    "updatedAt": "updated_at",
}


def _sanitize_sort(sort_field: str) -> str:
    # 过滤排序字段，默认使用 id
    return SORT_MAPPING.get(sort_field, "id")


def list_tenants(
    *,
    page: int,
    per_page: int,
    sort: str,
    order: str,
    q: Optional[str],
    table_name: str,
) -> Tuple[List[Dict[str, Any]], int]:
    # 分页查询租户列表，支持按 id/name 模糊搜索与禁用状态排序
    """列表查询，返回行与总数"""

    order_dir = "ASC" if order.upper() == "ASC" else "DESC"
    sort_col = _sanitize_sort(sort)
    offset = (page - 1) * per_page

    where: List[str] = []
    params: Dict[str, Any] = {}
    if q:
        where.append("(id LIKE :q OR name LIKE :q)")
        params["q"] = f"%{q}%"
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    count_sql = text(f"SELECT COUNT(*) AS cnt FROM `{table_name}` {where_sql}")
    list_sql = text(
        f"""
        SELECT id, name, disabled, created_at, updated_at
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


def get_tenant_by_id(*, tenant_id: str, table_name: str) -> Optional[Dict[str, Any]]:
    # 根据租户ID查询（精确匹配主键）
    sql = text(
        f"""
        SELECT id, name, disabled, created_at, updated_at
        FROM `{table_name}` WHERE id = :id
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        row = conn.execute(sql, {"id": tenant_id}).mappings().first()
    return dict(row) if row else None


def get_tenant_by_name(*, name: str, table_name: str) -> Optional[Dict[str, Any]]:
    # 根据租户名称查询（唯一约束）
    sql = text(
        f"""
        SELECT id, name, disabled, created_at, updated_at
        FROM `{table_name}` WHERE name = :name
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        row = conn.execute(sql, {"name": name}).mappings().first()
    return dict(row) if row else None


def create_tenant(
    *,
    payload: Dict[str, Any],
    table_name: str,
) -> Dict[str, Any]:
    # 创建租户并返回记录；若未提供 id 将自动生成 UUID
    """插入租户并返回插入后的记录"""

    tid = (payload.get("id") or __import__("uuid").uuid4().hex)[:64]
    now = datetime.now(timezone.utc)
    sql = text(
        f"""
        INSERT INTO `{table_name}`
        (id, name, disabled, created_at)
        VALUES (:id, :name, :disabled, :created_at)
        """
    )

    params = {
        "id": tid,
        "name": payload.get("name"),
        "disabled": int(bool(payload.get("disabled", False))),
        "created_at": now,
    }

    engine = get_mysql_engine()
    with engine.begin() as conn:
        conn.execute(sql, params)
        ret = conn.execute(
            text(
                f"SELECT id, name, disabled, created_at, updated_at FROM `{table_name}` WHERE id = :id"
            ),
            {"id": tid},
        ).mappings().first()
        return dict(ret)


def update_tenant(
    *,
    tenant_id: str,
    payload: Dict[str, Any],
    table_name: str,
) -> Optional[Dict[str, Any]]:
    # 更新租户基本信息（不可修改主键 id）
    """更新租户，如果不存在返回 None"""

    allowed_cols = [
        "name",
        "disabled",
    ]

    sets = []
    params: Dict[str, Any] = {"id": tenant_id}
    for col in allowed_cols:
        if col in payload and payload[col] is not None:
            # disabled 统一转为 tinyint(1)，确保与表结构一致
            if col == "disabled":
                params[col] = int(bool(payload[col]))
            else:
                params[col] = payload[col]
            sets.append(f"{col} = :{col}")

    if not sets:
        # 没有任何变更，直接返回当前记录
        return get_tenant_by_id(tenant_id=tenant_id, table_name=table_name)

    sql = text(f"UPDATE `{table_name}` SET " + ", ".join(sets) + " WHERE id = :id")
    engine = get_mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(sql, params)
        if result.rowcount == 0:
            return None
        ret = conn.execute(
            text(
                f"SELECT id, name, disabled, created_at, updated_at FROM `{table_name}` WHERE id = :id"
            ),
            {"id": tenant_id},
        ).mappings().first()
        return dict(ret) if ret else None


def delete_tenant(*, tenant_id: str, table_name: str) -> bool:
    # 删除租户（谨慎使用，可能涉及级联影响）
    sql = text(f"DELETE FROM `{table_name}` WHERE id = :id")
    engine = get_mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(sql, {"id": tenant_id})
        return result.rowcount > 0