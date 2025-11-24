from __future__ import annotations
from typing import Any, Dict, Optional, Tuple
from fastapi import HTTPException

from agentlz.config.settings import get_settings
from agentlz.repositories import document_repository as repo
from agentlz.app.deps.auth_deps import require_admin


def _get_table_and_header() -> Tuple[str, str]:
    """读取当前文档表名与租户请求头键名。

    返回：
    - `(table_name, tenant_header)` 元组；当未在配置中显式设置时，
      `table_name` 默认为 `document`，`tenant_header` 默认为 `X-Tenant-ID`。
    """
    s = get_settings()
    table_name = getattr(s, "document_table_name", "document")
    tenant_header = getattr(s, "tenant_id_header", "X-Tenant-ID")
    return table_name, tenant_header

def _ensure_authenticated(claims: Optional[Dict[str, Any]]) -> None:
    if not isinstance(claims, dict):
        raise HTTPException(status_code=401, detail="缺少或非法的 Authorization 头")


def get_document_service(*, doc_id: str, tenant_id: str, claims: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """按文档 ID 查询单条记录（按租户隔离）。

    参数：
    - `doc_id`: 文档主键 ID。
    - `tenant_id`: 租户标识，用于多租户数据隔离。

    返回：
    - 文档记录字典或 `None`；其中 `upload_time` 字段会被统一转换为字符串。
    """
    _ensure_authenticated(claims)
    table_name, _ = _get_table_and_header()
    row = repo.get_document_by_id(doc_id=doc_id, tenant_id=tenant_id, table_name=table_name)
    if row and row.get("upload_time") is not None:
        row["upload_time"] = str(row["upload_time"])
    return row


def update_document_service(*, doc_id: str, payload: Dict[str, Any], tenant_id: str, claims: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """更新文档信息（不可变更主键与租户字段）。

    参数：
    - `doc_id`: 文档主键 ID。
    - `payload`: 待更新的字段字典；具体允许字段以仓储层白名单为准
     （`uploaded_by_user_id`、`status`、`title`、`content`）。
    - `tenant_id`: 租户标识。

    返回：
    - 更新后的记录字典或 `None`；其中 `upload_time` 字段会被统一转换为字符串。
    """
    _ensure_authenticated(claims)
    table_name, _ = _get_table_and_header()
    require_admin(claims or {}, tenant_id)
    row = repo.update_document(doc_id=doc_id, payload=payload, tenant_id=tenant_id, table_name=table_name)
    if row and row.get("upload_time") is not None:
        row["upload_time"] = str(row["upload_time"])
    return row


def delete_document_service(*, doc_id: str, tenant_id: str, claims: Optional[Dict[str, Any]] = None) -> bool:
    """删除文档（按租户隔离）。

    参数：
    - `doc_id`: 文档主键 ID。
    - `tenant_id`: 租户标识。

    返回：
    - `True` 表示删除成功，`False` 表示未找到或删除失败。
    """
    _ensure_authenticated(claims)
    table_name, _ = _get_table_and_header()
    require_admin(claims or {}, tenant_id)
    return repo.delete_document(doc_id=doc_id, tenant_id=tenant_id, table_name=table_name)


def get_download_payload_service(*, doc_id: str, tenant_id: str, claims: Optional[Dict[str, Any]] = None) -> Optional[Tuple[str, str]]:
    """为下载场景组装内容与文件名。

    参数：
    - `doc_id`: 文档主键 ID。
    - `tenant_id`: 租户标识。

    返回：
    - 二元组 `(content, filename)`；当文档不存在时返回 `None`。
      其中 `filename` 由标题派生，后缀为 `.txt`，若标题为空则默认 `document.txt`。
    """
    _ensure_authenticated(claims)
    table_name, _ = _get_table_and_header()
    row = repo.get_document_by_id(doc_id=doc_id, tenant_id=tenant_id, table_name=table_name)
    if not row:
        return None
    title = (row.get("title") or "document").strip()
    content = str(row.get("content") or "")
    return content, f"{title}.txt"


def list_documents_service(
    *, page: int, per_page: int, sort: str, order: str, q: Optional[str], tenant_id: str, claims: Optional[Dict[str, Any]] = None
) -> Tuple[list[Dict[str, Any]], int]:
    """分页查询文档列表（按租户隔离，支持模糊搜索与排序）。

    参数：
    - `page`: 页码，从 1 开始。
    - `per_page`: 每页条数。
    - `sort`: 排序字段（由仓储层映射白名单过滤，非法字段回退为 `id`）。
    - `order`: 排序方向（`ASC` 或 `DESC`）。
    - `q`: 模糊搜索关键词，匹配标题与内容。
    - `tenant_id`: 租户标识。

    返回：
    - `(rows, total)`：记录列表与总条数；其中每条记录的 `upload_time`
      字段会被统一转换为字符串。
    """
    _ensure_authenticated(claims)
    table_name, _ = _get_table_and_header()
    rows, total = repo.list_documents(
        page=page,
        per_page=per_page,
        sort=sort,
        order=order,
        q=q,
        tenant_id=tenant_id,
        table_name=table_name,
    )
    for r in rows:
        if r.get("upload_time") is not None:
            r["upload_time"] = str(r["upload_time"])
    return rows, total


def create_document_service(*, payload: Dict[str, Any], tenant_id: str, claims: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """创建文档并返回插入后的记录。

    说明：
    - 当未在 `payload` 中提供 `id` 时，仓储层会自动生成一个 UUID。
    - `upload_time` 由系统写入当前时间。

    参数：
    - `payload`: 创建所需字段字典，例如 `title`、`content`、`uploaded_by_user_id`、`status` 等。
    - `tenant_id`: 租户标识。

    返回：
    - 新建的记录字典；其中 `upload_time` 字段会被统一转换为字符串。
    """
    _ensure_authenticated(claims)
    table_name, _ = _get_table_and_header()
    require_admin(claims or {}, tenant_id)
    row = repo.create_document(payload=payload, tenant_id=tenant_id, table_name=table_name)
    if row.get("upload_time") is not None:
        row["upload_time"] = str(row["upload_time"])
    return row
"""文档服务层（基于 MySQL，多租户隔离）

职责：
- 封装文档的业务逻辑，统一从配置读取表名与租户请求头，并通过仓储层执行 CRUD。
- 严格按 `tenant_id` 进行数据隔离，所有读写都必须携带租户参数。
- 统一将时间字段（例如 `upload_time`）转换为字符串，便于前端展示。
- 为下载场景组装返回内容与文件名。

约定：
- 服务层不直接书写 SQL，只调用 `agentlz.repositories.document_repository` 中的方法。
- 更新操作不允许修改主键 `id` 与隔离字段 `tenant_id`，允许字段以仓储层白名单为准。
- 表名默认 `document`，租户请求头默认 `X-Tenant-ID`，可通过配置覆盖。
"""