from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
import json
import uuid
from sqlalchemy import text
from agentlz.core.database import get_mysql_engine

DATASET_SORT_MAPPING = {
    "id": "id",
    "name": "name",
    "status": "status",
    "created_at": "created_at",
    "updated_at": "updated_at",
}

VERSION_SORT_MAPPING = {
    "id": "id",
    "created_at": "created_at",
    "updated_at": "updated_at",
}

CONTENT_SORT_MAPPING = {
    "id": "id",
    "status": "status",
    "created_at": "created_at",
    "updated_at": "updated_at",
    "finished_at": "finished_at",
}


def _now() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


def _sanitize_sort(sort_field: str, mapping: Dict[str, str], fallback: str) -> str:
    return mapping.get(str(sort_field or "").strip(), fallback)


def list_eva_datasets(
    *,
    page: int,
    per_page: int,
    sort: str,
    order: str,
    q: Optional[str],
    tenant_id: str,
    table_name: str,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    按租户分页查询测评数据集。

    参数：
    - page/per_page：分页参数。
    - sort/order：排序字段与方向。
    - q：可选关键字，按 name 模糊搜索。
    - tenant_id：目标租户ID。
    - table_name：数据集表名（支持配置覆盖）。

    返回：
    - (rows, total)：当前页数据与总数。
    """
    order_dir = "ASC" if str(order or "").upper() == "ASC" else "DESC"
    sort_col = _sanitize_sort(sort, DATASET_SORT_MAPPING, "id")
    offset = (max(1, int(page)) - 1) * max(1, int(per_page))
    where = ["tenant_id = :tenant_id"]
    params: Dict[str, Any] = {"tenant_id": tenant_id}
    if q:
        where.append("name LIKE :q")
        params["q"] = f"%{q}%"
    where_sql = "WHERE " + " AND ".join(where)
    count_sql = text(f"SELECT COUNT(*) AS cnt FROM `{table_name}` {where_sql}")
    list_sql = text(
        f"""
        SELECT id, tenant_id, scope, uploaded_by_user_id, status, name, data_json, total_count, created_at, updated_at
        FROM `{table_name}`
        {where_sql}
        ORDER BY {sort_col} {order_dir}
        LIMIT :limit OFFSET :offset
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        total = conn.execute(count_sql, params).scalar() or 0
        rows = conn.execute(
            list_sql, {**params, "limit": int(per_page), "offset": int(offset)}
        ).mappings().all()
    return [dict(r) for r in rows], int(total)


def get_eva_dataset_by_id(*, dataset_id: str, tenant_id: str, table_name: str) -> Optional[Dict[str, Any]]:
    """
    根据数据集ID查询单条测评集。

    参数：
    - dataset_id：测评集ID。
    - tenant_id：租户ID。
    - table_name：测评集表名。

    返回：
    - 命中返回数据字典，否则返回 None。
    """
    sql = text(
        f"""
        SELECT id, tenant_id, scope, uploaded_by_user_id, status, name, data_json, total_count, created_at, updated_at
        FROM `{table_name}`
        WHERE id = :id AND tenant_id = :tenant_id
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        row = conn.execute(sql, {"id": dataset_id, "tenant_id": tenant_id}).mappings().first()
    return dict(row) if row else None


def create_eva_dataset(*, payload: Dict[str, Any], tenant_id: str, table_name: str) -> Dict[str, Any]:
    """
    创建测评集记录。

    参数：
    - payload：包含 name/scope/status/data_json/total_count/uploaded_by_user_id。
    - tenant_id：租户ID。
    - table_name：测评集表名。

    返回：
    - 新创建的数据集完整记录。
    """
    dataset_id = str(payload.get("id") or uuid.uuid4().hex)[:64]
    sql = text(
        f"""
        INSERT INTO `{table_name}`
        (id, tenant_id, scope, uploaded_by_user_id, status, name, data_json, total_count, created_at, updated_at)
        VALUES
        (:id, :tenant_id, :scope, :uploaded_by_user_id, :status, :name, :data_json, :total_count, :created_at, :updated_at)
        """
    )
    now = _now()
    params = {
        "id": dataset_id,
        "tenant_id": tenant_id,
        "scope": str(payload.get("scope") or "tenant"),
        "uploaded_by_user_id": payload.get("uploaded_by_user_id"),
        "status": str(payload.get("status") or "ready"),
        "name": str(payload.get("name") or "").strip(),
        "data_json": str(payload.get("data_json") or "[]"),
        "total_count": int(payload.get("total_count") or 0),
        "created_at": now,
        "updated_at": now,
    }
    engine = get_mysql_engine()
    with engine.begin() as conn:
        conn.execute(sql, params)
        row = conn.execute(
            text(
                f"""
                SELECT id, tenant_id, scope, uploaded_by_user_id, status, name, data_json, total_count, created_at, updated_at
                FROM `{table_name}` WHERE id = :id AND tenant_id = :tenant_id
                """
            ),
            {"id": dataset_id, "tenant_id": tenant_id},
        ).mappings().first()
    return dict(row) if row else {}


def delete_eva_dataset(*, dataset_id: str, tenant_id: str, table_name: str) -> bool:
    """
    删除测评集记录。

    参数：
    - dataset_id：测评集ID。
    - tenant_id：租户ID。
    - table_name：测评集表名。

    返回：
    - True 表示已删除，False 表示不存在。
    """
    sql = text(f"DELETE FROM `{table_name}` WHERE id = :id AND tenant_id = :tenant_id")
    engine = get_mysql_engine()
    with engine.begin() as conn:
        res = conn.execute(sql, {"id": dataset_id, "tenant_id": tenant_id})
    return res.rowcount > 0


def create_eva_version(*, payload: Dict[str, Any], tenant_id: str, table_name: str) -> Dict[str, Any]:
    """
    创建测评版本快照记录。

    参数：
    - payload：包含 agent_id、prompt、document_ids_json、strategy_json、mcp_json、created_by_user_id。
    - tenant_id：租户ID。
    - table_name：版本表名。

    返回：
    - 新创建的版本记录。
    """
    sql = text(
        f"""
        INSERT INTO `{table_name}`
        (tenant_id, agent_id, created_by_user_id, prompt, document_ids_json, strategy_json, mcp_json, created_at, updated_at)
        VALUES
        (:tenant_id, :agent_id, :created_by_user_id, :prompt, :document_ids_json, :strategy_json, :mcp_json, :created_at, :updated_at)
        """
    )
    now = _now()
    params = {
        "tenant_id": tenant_id,
        "agent_id": int(payload.get("agent_id") or 0),
        "created_by_user_id": payload.get("created_by_user_id"),
        "prompt": str(payload.get("prompt") or ""),
        "document_ids_json": str(payload.get("document_ids_json") or "[]"),
        "strategy_json": str(payload.get("strategy_json") or "{}"),
        "mcp_json": str(payload.get("mcp_json") or "[]"),
        "created_at": now,
        "updated_at": now,
    }
    engine = get_mysql_engine()
    with engine.begin() as conn:
        conn.execute(sql, params)
        vid = conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()
        row = conn.execute(
            text(
                f"""
                SELECT id, tenant_id, agent_id, created_by_user_id, prompt, document_ids_json, strategy_json, mcp_json, created_at, updated_at
                FROM `{table_name}` WHERE id = :id AND tenant_id = :tenant_id
                """
            ),
            {"id": int(vid or 0), "tenant_id": tenant_id},
        ).mappings().first()
    return dict(row) if row else {}


def list_eva_versions(
    *,
    agent_id: int,
    tenant_id: str,
    page: int,
    per_page: int,
    sort: str,
    order: str,
    table_name: str,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    分页查询某个 Agent 的版本快照。

    参数：
    - agent_id：Agent 主键ID。
    - tenant_id：租户ID。
    - page/per_page：分页参数。
    - sort/order：排序参数。
    - table_name：版本表名。

    返回：
    - (rows, total)：版本列表与总数。
    """
    order_dir = "ASC" if str(order or "").upper() == "ASC" else "DESC"
    sort_col = _sanitize_sort(sort, VERSION_SORT_MAPPING, "id")
    offset = (max(1, int(page)) - 1) * max(1, int(per_page))
    count_sql = text(
        f"SELECT COUNT(*) AS cnt FROM `{table_name}` WHERE tenant_id = :tenant_id AND agent_id = :agent_id"
    )
    list_sql = text(
        f"""
        SELECT id, tenant_id, agent_id, created_by_user_id, prompt, document_ids_json, strategy_json, mcp_json, created_at, updated_at
        FROM `{table_name}`
        WHERE tenant_id = :tenant_id AND agent_id = :agent_id
        ORDER BY {sort_col} {order_dir}
        LIMIT :limit OFFSET :offset
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        total = conn.execute(count_sql, {"tenant_id": tenant_id, "agent_id": int(agent_id)}).scalar() or 0
        rows = conn.execute(
            list_sql,
            {"tenant_id": tenant_id, "agent_id": int(agent_id), "limit": int(per_page), "offset": int(offset)},
        ).mappings().all()
    return [dict(r) for r in rows], int(total)


def create_eva_content(*, payload: Dict[str, Any], tenant_id: str, table_name: str) -> Dict[str, Any]:
    """
    创建测评运行结果主记录。

    参数：
    - payload：包含 eva_json_id/eva_version_id/status/total_count/completed_count/content_json/started_at/finished_at。
    - tenant_id：租户ID。
    - table_name：结果表名。

    返回：
    - 新建结果记录。
    """
    sql = text(
        f"""
        INSERT INTO `{table_name}`
        (tenant_id, eva_json_id, eva_version_id, status, total_count, completed_count, content_json, started_at, finished_at, created_at, updated_at)
        VALUES
        (:tenant_id, :eva_json_id, :eva_version_id, :status, :total_count, :completed_count, :content_json, :started_at, :finished_at, :created_at, :updated_at)
        """
    )
    now = _now()
    params = {
        "tenant_id": tenant_id,
        "eva_json_id": str(payload.get("eva_json_id") or ""),
        "eva_version_id": int(payload.get("eva_version_id") or 0),
        "status": str(payload.get("status") or "queued"),
        "total_count": int(payload.get("total_count") or 0),
        "completed_count": int(payload.get("completed_count") or 0),
        "content_json": str(payload.get("content_json") or "[]"),
        "started_at": payload.get("started_at"),
        "finished_at": payload.get("finished_at"),
        "created_at": now,
        "updated_at": now,
    }
    engine = get_mysql_engine()
    with engine.begin() as conn:
        conn.execute(sql, params)
        cid = conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()
        row = conn.execute(
            text(
                f"""
                SELECT id, tenant_id, eva_json_id, eva_version_id, status, total_count, completed_count, content_json,
                       started_at, finished_at, created_at, updated_at
                FROM `{table_name}` WHERE id = :id AND tenant_id = :tenant_id
                """
            ),
            {"id": int(cid or 0), "tenant_id": tenant_id},
        ).mappings().first()
    return dict(row) if row else {}


def get_eva_content_by_id(*, content_id: int, tenant_id: str, table_name: str) -> Optional[Dict[str, Any]]:
    """
    按主键查询单次测评结果。

    参数：
    - content_id：结果ID。
    - tenant_id：租户ID。
    - table_name：结果表名。

    返回：
    - 命中返回字典，否则 None。
    """
    sql = text(
        f"""
        SELECT id, tenant_id, eva_json_id, eva_version_id, status, total_count, completed_count, content_json,
               started_at, finished_at, created_at, updated_at
        FROM `{table_name}` WHERE id = :id AND tenant_id = :tenant_id
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        row = conn.execute(sql, {"id": int(content_id), "tenant_id": tenant_id}).mappings().first()
    return dict(row) if row else None


def update_eva_content(*, content_id: int, tenant_id: str, payload: Dict[str, Any], table_name: str) -> Optional[Dict[str, Any]]:
    """
    更新单次测评结果的状态、进度与内容。

    参数：
    - content_id：结果ID。
    - tenant_id：租户ID。
    - payload：允许字段 status/total_count/completed_count/content_json/started_at/finished_at/updated_at。
    - table_name：结果表名。

    返回：
    - 更新后记录；不存在返回 None。
    """
    allowed_cols = ["status", "total_count", "completed_count", "content_json", "started_at", "finished_at", "updated_at"]
    sets: List[str] = []
    params: Dict[str, Any] = {"id": int(content_id), "tenant_id": tenant_id}
    for col in allowed_cols:
        if col in payload:
            sets.append(f"{col} = :{col}")
            params[col] = payload[col]
    if not sets:
        return get_eva_content_by_id(content_id=int(content_id), tenant_id=tenant_id, table_name=table_name)
    sql = text(
        f"UPDATE `{table_name}` SET " + ", ".join(sets) + " WHERE id = :id AND tenant_id = :tenant_id"
    )
    engine = get_mysql_engine()
    with engine.begin() as conn:
        res = conn.execute(sql, params)
        if res.rowcount == 0:
            return None
        row = conn.execute(
            text(
                f"""
                SELECT id, tenant_id, eva_json_id, eva_version_id, status, total_count, completed_count, content_json,
                       started_at, finished_at, created_at, updated_at
                FROM `{table_name}` WHERE id = :id AND tenant_id = :tenant_id
                """
            ),
            {"id": int(content_id), "tenant_id": tenant_id},
        ).mappings().first()
    return dict(row) if row else None


def append_eva_content_items(
    *,
    content_id: int,
    tenant_id: str,
    new_items: List[Dict[str, Any]],
    completed_count: int,
    table_name: str,
) -> Optional[Dict[str, Any]]:
    """
    将新结果项追加到 content_json，并同步更新 completed_count。

    参数：
    - content_id：结果ID。
    - tenant_id：租户ID。
    - new_items：待追加结果数组。
    - completed_count：最新完成数。
    - table_name：结果表名。

    返回：
    - 更新后的记录；若记录不存在返回 None。
    """
    cur = get_eva_content_by_id(content_id=int(content_id), tenant_id=tenant_id, table_name=table_name)
    if not cur:
        return None
    content_json = str(cur.get("content_json") or "[]")
    try:
        current_items = json.loads(content_json)
        if not isinstance(current_items, list):
            current_items = []
    except Exception:
        current_items = []
    current_items.extend(new_items or [])
    return update_eva_content(
        content_id=int(content_id),
        tenant_id=tenant_id,
        payload={
            "content_json": json.dumps(current_items, ensure_ascii=False),
            "completed_count": int(completed_count),
            "updated_at": _now(),
        },
        table_name=table_name,
    )


def list_eva_contents(
    *,
    tenant_id: str,
    agent_id: int,
    eva_version_id: Optional[int],
    page: int,
    per_page: int,
    sort: str,
    order: str,
    content_table_name: str,
    version_table_name: str,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    分页查询某 Agent 的测评结果列表。

    参数：
    - tenant_id：租户ID。
    - agent_id：Agent ID。
    - eva_version_id：可选版本过滤。
    - page/per_page：分页参数。
    - sort/order：排序参数。
    - content_table_name：结果表名。
    - version_table_name：版本表名（用于关联过滤 agent_id）。

    返回：
    - (rows, total)：结果列表与总数。
    """
    order_dir = "ASC" if str(order or "").upper() == "ASC" else "DESC"
    sort_col = _sanitize_sort(sort, CONTENT_SORT_MAPPING, "id")
    offset = (max(1, int(page)) - 1) * max(1, int(per_page))
    where = [
        "c.tenant_id = :tenant_id",
        "v.agent_id = :agent_id",
    ]
    params: Dict[str, Any] = {"tenant_id": tenant_id, "agent_id": int(agent_id)}
    if eva_version_id is not None:
        where.append("c.eva_version_id = :eva_version_id")
        params["eva_version_id"] = int(eva_version_id)
    where_sql = "WHERE " + " AND ".join(where)
    count_sql = text(
        f"""
        SELECT COUNT(*) AS cnt
        FROM `{content_table_name}` c
        INNER JOIN `{version_table_name}` v ON c.eva_version_id = v.id AND c.tenant_id = v.tenant_id
        {where_sql}
        """
    )
    list_sql = text(
        f"""
        SELECT c.id, c.tenant_id, c.eva_json_id, c.eva_version_id, c.status, c.total_count, c.completed_count,
               c.content_json, c.started_at, c.finished_at, c.created_at, c.updated_at
        FROM `{content_table_name}` c
        INNER JOIN `{version_table_name}` v ON c.eva_version_id = v.id AND c.tenant_id = v.tenant_id
        {where_sql}
        ORDER BY c.{sort_col} {order_dir}
        LIMIT :limit OFFSET :offset
        """
    )
    engine = get_mysql_engine()
    with engine.connect() as conn:
        total = conn.execute(count_sql, params).scalar() or 0
        rows = conn.execute(
            list_sql, {**params, "limit": int(per_page), "offset": int(offset)}
        ).mappings().all()
    return [dict(r) for r in rows], int(total)
