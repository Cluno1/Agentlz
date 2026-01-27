"""Model 仓储（MySQL）

职责
- 提供模型表的增删改查（CRUD）与分页列表能力
- 所有 SQL 使用参数化形式（sqlalchemy.text + 绑定参数），避免 SQL 注入
- 对排序字段进行白名单映射，防止外部传入任意列名参与 ORDER BY

表结构对齐（参见 `docs/deploy/sql/init_mysql.sql` 的 `model` 表）
- 主键：`id` bigint(20)
- 唯一：`name`（唯一索引）
- 字段：`price`、`description`、`manufacturer`、`tags(JSON Array)`
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import json
from sqlalchemy import text
from agentlz.core.database import get_mysql_engine

# 排序字段白名单映射（外部字段名 -> 数据库列名）
SORT_MAPPING = {
    "id": "id",
    "name": "name",
    "price": "price",
}

def _sanitize_sort(sort_field: str) -> str:
    # 过滤排序字段，未命中时默认按 id 排序
    return SORT_MAPPING.get(sort_field, "id")

def list_models(
    *,
    page: int,
    per_page: int,
    sort: str,
    order: str,
    q: Optional[str],
    table_name: str,
) -> Tuple[List[Dict[str, Any]], int]:
    """分页列出模型

    参数：
    - page、per_page：分页参数（页码从 1 开始）
    - sort：排序字段（白名单：id/name/price）
    - order：排序方向（ASC/DESC）
    - q：名称或描述模糊查询
    - table_name：表名
    """
    order_dir = "ASC" if str(order or "").upper() == "ASC" else "DESC"
    sort_col = _sanitize_sort(sort)
    offset = (max(1, int(page)) - 1) * max(1, int(per_page))
    where: List[str] = []
    params: Dict[str, Any] = {}
    if q:
        where.append(
            "(name LIKE :q OR description LIKE :q OR manufacturer LIKE :q OR JSON_SEARCH(tags, 'one', :q, NULL) IS NOT NULL OR CAST(tags AS CHAR) LIKE :q)"
        )
        params["q"] = f"%{q}%"
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    count_sql = text(f"SELECT COUNT(*) AS cnt FROM `{table_name}` {where_sql}")
    list_sql = text(
        f"""
        SELECT id, name, price, description, manufacturer, tags
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
    out = [dict(r) for r in rows]
    for r in out:
        t = r.get("tags")
        if isinstance(t, str):
            try:
                r["tags"] = json.loads(t)
            except Exception:
                r["tags"] = []
        elif not isinstance(t, list):
            r["tags"] = [] if t is None else []
    return out, int(total)

def get_model_by_id(*, model_id: int, table_name: str) -> Optional[Dict[str, Any]]:
    """按主键查询单条模型记录。"""
    sql = text(
        f"""
        SELECT id, name, price, description, manufacturer, tags
        FROM `{table_name}` WHERE id = :id
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        row = conn.execute(sql, {"id": int(model_id)}).mappings().first()
    if not row:
        return None
    ret = dict(row)
    t = ret.get("tags")
    if isinstance(t, str):
        try:
            ret["tags"] = json.loads(t)
        except Exception:
            ret["tags"] = []
    elif not isinstance(t, list):
        ret["tags"] = [] if t is None else []
    return ret

def get_model_by_name(*, name: str, table_name: str) -> Optional[Dict[str, Any]]:
    """按名称查询模型（唯一索引）。"""
    sql = text(
        f"""
        SELECT id, name, price, description, manufacturer, tags
        FROM `{table_name}` WHERE name = :name
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        row = conn.execute(sql, {"name": name}).mappings().first()
    if not row:
        return None
    ret = dict(row)
    t = ret.get("tags")
    if isinstance(t, str):
        try:
            ret["tags"] = json.loads(t)
        except Exception:
            ret["tags"] = []
    elif not isinstance(t, list):
        ret["tags"] = [] if t is None else []
    return ret

def create_model(
    *,
    payload: Dict[str, Any],
    table_name: str,
) -> Dict[str, Any]:
    """创建模型并回读插入后的完整记录。"""
    sql = text(
        f"""
        INSERT INTO `{table_name}` (name, price, description, manufacturer, tags)
        VALUES (:name, :price, :description, :manufacturer, :tags)
        """
    )
    params = {
        "name": payload.get("name"),
        "price": payload.get("price"),
        "description": payload.get("description"),
        "manufacturer": payload.get("manufacturer"),
        "tags": json.dumps(payload.get("tags", []), ensure_ascii=False) if payload.get("tags") is not None else json.dumps([], ensure_ascii=False),
    }
    engine = get_mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(sql, params)
        new_id = result.lastrowid
        ret = conn.execute(
            text(
                f"SELECT id, name, price, description, manufacturer, tags FROM `{table_name}` WHERE id = :id"
            ),
            {"id": new_id},
        ).mappings().first()
        row = dict(ret)
        t = row.get("tags")
        if isinstance(t, str):
            try:
                row["tags"] = json.loads(t)
            except Exception:
                row["tags"] = []
        elif not isinstance(t, list):
            row["tags"] = [] if t is None else []
        return row

def update_model(
    *,
    model_id: int,
    payload: Dict[str, Any],
    table_name: str,
) -> Optional[Dict[str, Any]]:
    """更新模型；不支持修改主键。"""
    allowed_cols = ["name", "price", "description", "manufacturer", "tags"]
    sets: List[str] = []
    params: Dict[str, Any] = {"id": int(model_id)}
    for col in allowed_cols:
        if col in payload and payload[col] is not None:
            val = payload[col]
            if col == "tags":
                if isinstance(val, (list, dict)):
                    val = json.dumps(val, ensure_ascii=False)
                elif not isinstance(val, str):
                    val = json.dumps([], ensure_ascii=False)
            sets.append(f"{col} = :{col}")
            params[col] = val
    if not sets:
        return get_model_by_id(model_id=model_id, table_name=table_name)
    sql = text(f"UPDATE `{table_name}` SET " + ", ".join(sets) + " WHERE id = :id")
    engine = get_mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(sql, params)
        if result.rowcount == 0:
            return None
        ret = conn.execute(
            text(f"SELECT id, name, price, description, manufacturer, tags FROM `{table_name}` WHERE id = :id"),
            {"id": int(model_id)},
        ).mappings().first()
        if not ret:
            return None
        row = dict(ret)
        t = row.get("tags")
        if isinstance(t, str):
            try:
                row["tags"] = json.loads(t)
            except Exception:
                row["tags"] = []
        elif not isinstance(t, list):
            row["tags"] = [] if t is None else []
        return row

def delete_model(*, model_id: int, table_name: str) -> bool:
    """按主键删除模型。"""
    sql = text(f"DELETE FROM `{table_name}` WHERE id = :id")
    engine = get_mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(sql, {"id": int(model_id)})
        return result.rowcount > 0
