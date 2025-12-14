from __future__ import annotations

"""RAG 仓储（MySQL）

职责
- 管理与 Agent 相关的 RAG 配置数据（如名称与元信息 `meta`）
- 所有 SQL 使用参数化（`sqlalchemy.text` + 绑定参数），避免 SQL 注入

表结构（建议）
- 主键：`id` bigint(20)
- 外键：`agent_id` 指向 `agent` 表
- 字段：`name`、`meta`（JSON 字符串）、`created_at`

使用约定
- `meta` 入库统一为 JSON 字符串；读取时尽量反序列化为对象
"""

from typing import Any, Dict, Optional, Tuple, List
from datetime import datetime, timezone, timedelta
import json
from sqlalchemy import text

from agentlz.core.database import get_mysql_engine


# 排序字段白名单映射（外部字段名 -> 数据库列名）
SORT_MAPPING = {
    "id": "id",
    "name": "name",
    "createdAt": "created_at",
}


def _sanitize_sort(sort_field: str) -> str:
    """过滤排序字段，未命中时默认按 `created_at` 排序"""
    return SORT_MAPPING.get(sort_field, "created_at")


def create_record(*, payload: Dict[str, Any], table_name: str) -> Dict[str, Any]:
    """创建 Record（agent_id 必填，name/meta 可选）并回读新建行

    参数：
    - payload：包含 `agent_id`、`name`（可选）、`meta`（可选）的字典
    - table_name：目标表名（如 `record`）

    返回：
    - 新建行的完整字典，字段包含：`id`、`agent_id`、`name`、`meta`、`created_at`

    说明：
    - `name` 未提供时使用默认值 `未命名记录`
    - `meta` 入库统一为 JSON 字符串；回读后尽量反序列化为对象
    - 通过事务插入并立即回读，保证返回的是落库后的实际数据
    """
    # 记录创建时间（中国标准时间）
    now = datetime.now(timezone(timedelta(hours=8)))

    # 统一序列化 meta 字段为 JSON 字符串，确保入库兼容性
    meta_val = payload.get("meta")
    if isinstance(meta_val, (dict, list)):
        meta_str = json.dumps(meta_val, ensure_ascii=False)
    elif meta_val is None:
        meta_str = json.dumps({}, ensure_ascii=False)
    else:
        # 允许传入字符串或可转换为字符串的对象
        meta_str = str(meta_val)

    # 处理 name 默认值（表定义为 NOT NULL）
    name_val = payload.get("name")
    if name_val is None or str(name_val).strip() == "":
        name_val = "未命名记录"

    # 使用参数化 SQL，避免注入风险
    sql = text(
        f"""
        INSERT INTO `{table_name}`
        (agent_id, name, meta, created_at)
        VALUES (:agent_id, :name, :meta, :created_at)
        """
    )

    # 绑定参数，确保类型安全与可维护性
    params = {
        "agent_id": int(payload.get("agent_id")),
        "name": name_val,
        "meta": meta_str,
        "created_at": now,
    }

    engine = get_mysql_engine()
    with engine.begin() as conn:
        # 事务插入，确保失败时整体回滚
        result = conn.execute(sql, params)
        new_id = result.lastrowid
        # 插入后立即回读完整记录，便于调用方直接使用
        ret = conn.execute(
            text(
                f"SELECT id, agent_id, name, meta, created_at FROM `{table_name}` WHERE id = :id"
            ),
            {"id": new_id},
        ).mappings().first()
        row = dict(ret) if ret else {}

    # 尝试把字符串形式的 meta 恢复为对象，提升上层易用性
    m = row.get("meta")
    if isinstance(m, str):
        try:
            row["meta"] = json.loads(m)
        except Exception:
            # 容错：若非合法 JSON 则保留原字符串
            pass
    return row


def get_record_by_id(*, record_id: int, table_name: str) -> Optional[Dict[str, Any]]:
    """按主键查询单条 Record

    参数：
    - record_id：记录主键ID
    - table_name：表名

    返回：
    - 记录字典（若存在），并尝试将 `meta` 反序列化；不存在返回 None
    """
    sql = text(
        f"""
        SELECT id, agent_id, name, meta, created_at
        FROM `{table_name}` WHERE id = :id
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        ret = conn.execute(sql, {"id": record_id}).mappings().first()
    if not ret:
        return None
    row = dict(ret)
    m = row.get("meta")
    if isinstance(m, str):
        try:
            row["meta"] = json.loads(m)
        except Exception:
            pass
    return row



def update_record(*, record_id: int, payload: Dict[str, Any], table_name: str) -> Optional[Dict[str, Any]]:
    """更新 Record（允许修改 name/meta）并回读

    参数：
    - record_id：记录主键ID
    - payload：更新内容，仅支持 `name`、`meta`
    - table_name：表名

    返回：
    - 更新后的记录字典；若未命中或无变更返回 None/当前行
    注意：
    - 不允许修改 `agent_id`，避免跨关联迁移
    """
    allowed_cols = ["name", "meta"]
    sets: List[str] = []
    params: Dict[str, Any] = {"id": record_id}
    for col in allowed_cols:
        if col in payload and payload[col] is not None:
            val = payload[col]
            if col == "meta":
                if isinstance(val, (dict, list)):
                    val = json.dumps(val, ensure_ascii=False)
                elif val is None:
                    val = json.dumps({}, ensure_ascii=False)
                else:
                    val = str(val)
            elif col == "name":
                if str(val).strip() == "":
                    val = "未命名记录"
            sets.append(f"{col} = :{col}")
            params[col] = val

    if not sets:
        return get_record_by_id(record_id=record_id, table_name=table_name)

    sql = text(f"UPDATE `{table_name}` SET " + ", ".join(sets) + " WHERE id = :id")
    engine = get_mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(sql, params)
        if result.rowcount == 0:
            return None
        ret = conn.execute(
            text(
                f"SELECT id, agent_id, name, meta, created_at FROM `{table_name}` WHERE id = :id"
            ),
            {"id": record_id},
        ).mappings().first()
        row = dict(ret) if ret else None
    if row and isinstance(row.get("meta"), str):
        try:
            row["meta"] = json.loads(row["meta"])  # type: ignore[index]
        except Exception:
            pass
    return row


def delete_record(*, record_id: int, table_name: str) -> bool:
    """按主键删除 Record

    参数：
    - record_id：记录主键ID
    - table_name：表名

    返回：
    - 删除成功返回 True，否则 False
    """
    sql = text(f"DELETE FROM `{table_name}` WHERE id = :id")
    engine = get_mysql_engine()
    with engine.begin() as conn:
        result = conn.execute(sql, {"id": record_id})
        return result.rowcount > 0


def list_records_by_agent(
    *,
    agent_id: int,
    page: int,
    per_page: int,
    sort: str,
    order: str,
    q: Optional[str],
    table_name: str,
) -> Tuple[List[Dict[str, Any]], int]:
    """分页查询某 Agent 下的 Record 列表

    参数：
    - agent_id：所属 Agent 主键
    - page、per_page：分页参数
    - sort：排序字段（白名单：id/name/createdAt）
    - order：排序方向（ASC/DESC）
    - q：可选名称模糊查询
    - table_name：表名

    返回：
    - (rows, total) 二元组；`rows` 每行为字典，含 `id/agent_id/name/meta/created_at`
    """
    order_dir = "ASC" if str(order or "").upper() == "ASC" else "DESC"
    sort_col = _sanitize_sort(sort)
    offset = (page - 1) * per_page

    where = ["agent_id = :agent_id"]
    params: Dict[str, Any] = {"agent_id": int(agent_id)}
    if q:
        where.append("name LIKE :q")
        params["q"] = f"%{q}%"
    where_sql = "WHERE " + " AND ".join(where)

    count_sql = text(f"SELECT COUNT(*) AS cnt FROM `{table_name}` {where_sql}")
    list_sql = text(
        f"""
        SELECT id, agent_id, name, meta, created_at
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
    out: List[Dict[str, Any]] = [dict(r) for r in rows]
    for r in out:
        m = r.get("meta")
        if isinstance(m, str):
            try:
                r["meta"] = json.loads(m)
            except Exception:
                pass
    return out, int(total)


def list_records_by_meta_and_agent_id(
    *,
    agent_id: int,
    meta_keyword: Optional[str],
    page: int,
    per_page: int,
    sort: str,
    order: str,
    table_name: str,
) -> Tuple[List[Dict[str, Any]], int]:
    """按 `agent_id` 与 `meta` 关键字分页查询 Record 列表

    参数：
    - agent_id：所属 Agent 主键
    - meta_keyword：`meta` 关键字（字符串匹配，LIKE），为空则忽略该条件
    - page、per_page：分页参数（页码从 1 开始）
    - sort：排序字段（白名单：id/name/createdAt），默认建议传 `createdAt`
    - order：排序方向（ASC/DESC），默认倒序 `DESC`
    - table_name：表名

    返回：
    - (rows, total) 二元组；`rows` 每行为字典，仅包含 `id/agent_id/name/created_at`

    说明：
    - 安全：所有用户输入均通过绑定参数传递，避免 SQL 注入
    - 性能：分页查询先统计总数，再按偏移量拉取当前页数据
    """
    order_dir = "ASC" if str(order or "").upper() == "ASC" else "DESC"
    sort_col = _sanitize_sort(sort)
    offset = (max(1, int(page)) - 1) * max(1, int(per_page))

    where = ["agent_id = :agent_id"]
    params: Dict[str, Any] = {"agent_id": int(agent_id)}
    if meta_keyword:
        where.append("meta LIKE :meta_q")
        params["meta_q"] = f"%{meta_keyword}%"
    where_sql = "WHERE " + " AND ".join(where)

    count_sql = text(f"SELECT COUNT(*) AS cnt FROM `{table_name}` {where_sql}")
    list_sql = text(
        f"""
        SELECT id, agent_id, name, created_at
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
    out: List[Dict[str, Any]] = [dict(r) for r in rows]
    return out, int(total)