from __future__ import annotations
from typing import Any, Dict, Optional, Tuple
from fastapi import HTTPException
import re
from agentlz.config.settings import get_settings
from agentlz.core.logger import setup_logging
from agentlz.repositories import document_repository as repo
from agentlz.repositories import user_repository as user_repo
from agentlz.repositories import user_doc_perm_repository as perm_repo
from agentlz.repositories import agent_document_repository as agdoc_repo
from agentlz.schemas.document import DocumentUpload

from agentlz.services.chunk_embeddings_service import create_chunk_embedding_service, split_markdown_into_chunks, search_similar_chunks_service
from agentlz.services.cos_service import upload_document_to_cos, get_origin_url_from_save_https
from agentlz.core.external_services import publish_to_rabbitmq
from markitdown import MarkItDown

logger = setup_logging()

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


suffix_map = {
    "pdf": ".pdf", "doc": ".doc", "docx": ".docx", "md": ".md", "txt": ".txt",
    "ppt": ".ppt", "pptx": ".pptx", "xls": ".xls", "xlsx": ".xlsx", "csv": ".csv",
}
ext_map = {
    "pdf": ".pdf",
    "doc": ".doc",
    "docx": ".docx",
            "md": ".md",
            "txt": ".txt",
            "ppt": ".ppt",
            "pptx": ".pptx",
            "xls": ".xls",
            "xlsx": ".xlsx",
            "csv": ".csv",
}


def clean_filename(data: dict, max_len: int = 200) -> str:
    """清理文档标题，生成安全的文件名

    1. 清理非法字符（保留空格、中划线、下划线）
    2. 去掉与文档类型不同的后缀（例如 .docx 保留 .docx）
    3. 限制总长度（默认200字符）

    :param data: 包含标题和文档类型的字典
    :param max_len: 最大文件名长度（默认200）
    :return: 清理后的安全文件名
    """

    raw_title = data.get("title", "").strip()
    doc_type = data.get("document_type", "").lower()

    try:
        ext = suffix_map.get(doc_type, "")          # 本次要拼的后缀
    except KeyError:
        raise HTTPException(
            status_code=400, detail=f"不支持的文档类型: {doc_type}")

    # 1. 清理非法字符
    safe_name = re.sub(r'[<>:\"/\\|?*\x00-\x1f]', '_', raw_title)
    safe_name = safe_name.strip('. ')
    safe_name = re.sub(r'\s+', ' ', safe_name)

    # 2. 去掉自带后缀
    for suffix in sorted(suffix_map.values(), key=len, reverse=True):
        if safe_name.lower().endswith(suffix.lower()):

            safe_name = safe_name[:-len(suffix)]

    # 3. 长度截断
    if max_len > 0:
        safe_name = safe_name[:max_len].rstrip()

    # 4. 拼回后缀
    return f"{safe_name}{ext}"


def _list_self_documents(
    *,
    page: int,
    per_page: int,
    sort: str,
    order: str,
    q: Optional[str],
    filters: Optional[Dict[str, Any]],
    user_id: int,
    table_name: str,
) -> Tuple[list[Dict[str, Any]], int]:
    s = get_settings()
    user_table_name = getattr(s, "user_table_name", "users")
    tenant_table_name = "tenant"
    rows, total = repo.list_self_documents_with_names(
        page=page,
        per_page=per_page,
        sort=sort,
        order=order,
        q=q,
        filters=filters,
        user_id=user_id,
        table_name=table_name,
        user_table_name=user_table_name,
        tenant_table_name=tenant_table_name,
    )
    return rows, total


def _list_tenant_documents_with_permission(
    *,
    page: int,
    per_page: int,
    sort: str,
    order: str,
    q: Optional[str],
    filters: Optional[Dict[str, Any]],
    user_id: int,
    tenant_id: str,
    table_name: str,
) -> Tuple[list[Dict[str, Any]], int]:
    s = get_settings()
    user_table_name = getattr(s, "user_table_name", "users")
    tenant_table_name = "tenant"
    perm_table_name = "user_doc_permission"
    rows, total = repo.list_tenant_documents_with_permission_with_names(
        page=page,
        per_page=per_page,
        sort=sort,
        order=order,
        q=q,
        filters=filters,
        user_id=user_id,
        tenant_id=tenant_id,
        table_name=table_name,
        perm_table_name=perm_table_name,
        user_table_name=user_table_name,
        tenant_table_name=tenant_table_name,
    )
    return rows, total


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
    """确保请求包含有效认证信息。

    参数：
    - `claims`: 用户认证 claims，包含用户ID等信息。

    抛出：
    - `HTTPException(401)`：若 `claims` 为空或不是字典类型。
    """
    if not claims or not isinstance(claims, dict):
        raise HTTPException(status_code=401, detail="缺少或非法的 Authorization 头")

# 检查文档访问权限


def _check_document_access_permission(
    *,
    document: Dict[str, Any],
    current_user_id: int,
    tenant_id: str
) -> bool:
    """检查用户是否有权限查看文档。

    权限检查逻辑（按优先级）：
    1. 如果文档的 `tenant_id` 是 'system'，则可以查看
    2. 如果用户是文档的上传者，则可以查看
    3. 如果用户在 user_doc_permission 表中有 admin 或 read 权限，则可以查看
    4. 如果用户是租户管理员且与文档在同一租户，则可以查看
    5. 其他情况不允许查看

    参数：
    - `document`: 文档记录
    - `current_user_id`: 当前用户ID
    - `tenant_id`: 租户标识
    - `claims`: 用户认证信息

    返回：
    - `True` 有权限查看，`False` 无权限查看
    """
    if not document:
        return False

    # 1. 如果文档是 'system'，则可以查看
    if document.get("tenant_id") == "system":
        return True

    # 2. 检查是否是文档上传者
    uploaded_by_user_id = document.get("uploaded_by_user_id")
    if uploaded_by_user_id and uploaded_by_user_id == current_user_id:
        return True

    # 3. 检查 user_doc_permission 表中的权限
    from agentlz.config.settings import get_settings
    s = get_settings()
    perm_table = getattr(
        s, "user_doc_permission_table_name", "user_doc_permissions")
    perm_record = perm_repo.get_perm_by_user_doc(
        user_id=current_user_id,
        doc_id=document.get("id"),
        table_name=perm_table
    )
    if perm_record:
        perm = perm_record.get("perm")
        if perm in ["admin", "read"]:
            return True

    # 4. 检查用户是否是租户管理员且在同一租户
    user_info = user_repo.get_user_by_id(
        user_id=current_user_id,
        tenant_id=tenant_id,
        table_name="users"
    )
    if user_info and user_info.get("role") == "admin" and user_info.get("tenant_id") == tenant_id:
        return True

    return False


# 检查文档更新或删除权限
def _check_document_update_delete_permission(
    *,
    document: Dict[str, Any],
    current_user_id: int,
    tenant_id: str
) -> bool:
    """检查用户是否有权限更新或删除文档。

    权限检查逻辑（按优先级）：
    1. 如果用户是文档的上传者，则可以更新或删除
    2. 如果用户在 user_doc_permission 表中有 admin 或 write 权限，则可以更新或删除
    3. 如果用户是租户管理员且与文档在同一租户，则可以更新或删除
    4. 其他情况不允许更新或删除

    参数：
    - `document`: 文档记录
    - `current_user_id`: 当前用户ID
    - `tenant_id`: 租户标识

    返回：
    - `True` 有权限更新或删除，`False` 无权限更新或删除
    """
    if not document:
        return False

    # 1. 检查是否是文档上传者
    uploaded_by_user_id = document.get("uploaded_by_user_id")
    if uploaded_by_user_id and uploaded_by_user_id == current_user_id:
        return True

    # 2. 检查 user_doc_permission 表中的权限（需要 admin 或 write 权限）
    from agentlz.config.settings import get_settings
    s = get_settings()
    perm_table = getattr(
        s, "user_doc_permission_table_name", "user_doc_permissions")
    perm_record = perm_repo.get_perm_by_user_doc(
        user_id=current_user_id,
        doc_id=document.get("id"),
        table_name=perm_table
    )
    if perm_record:
        perm = perm_record.get("perm")
        if perm in ["admin", "write"]:
            return True

    # 3. 检查用户是否是租户管理员且在同一租户
    user_info = user_repo.get_user_by_id(
        user_id=current_user_id,
        tenant_id=tenant_id,
        table_name="users"
    )
    if user_info and user_info.get("role") == "admin" and user_info.get("tenant_id") == tenant_id:
        return True

    return False


def get_document_service(*, doc_id: str, tenant_id: str, claims: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    _ensure_authenticated(claims)
    table_name, _ = _get_table_and_header()

    s = get_settings()
    user_table_name = getattr(s, "user_table_name", "users")
    tenant_table_name = "tenant"

    current_user_id = None
    if claims and "sub" in claims:
        try:
            current_user_id = int(claims["sub"])
        except (ValueError, TypeError):
            current_user_id = None
    if current_user_id is None:
        raise HTTPException(status_code=401, detail="无法获取用户身份信息")

    row = repo.get_document_with_names_by_id(
        doc_id=doc_id,
        tenant_id=tenant_id,
        table_name=table_name,
        user_table_name=user_table_name,
        tenant_table_name=tenant_table_name,
    )

    if not row:
        any_row = repo.get_document_with_names_by_id_any_tenant(
            doc_id=doc_id,
            table_name=table_name,
            user_table_name=user_table_name,
            tenant_table_name=tenant_table_name,
        )
        if any_row and any_row.get("uploaded_by_user_id") == current_user_id:
            row = any_row
        else:
            return None

    if not _check_document_access_permission(
        document=row,
        current_user_id=current_user_id,
        tenant_id=tenant_id
    ):
        raise HTTPException(status_code=403, detail="没有权限查看此文档")

    if row.get("upload_time") is not None:
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

    # 获取当前用户ID（从claims中获取）
    current_user_id = None
    if claims and "sub" in claims:
        # 假设 claims 中的 sub 字段包含用户ID
        try:
            current_user_id = int(claims["sub"])
        except (ValueError, TypeError):
            current_user_id = None

    # 如果没有用户ID，无法验证权限
    if current_user_id is None:
        raise HTTPException(status_code=401, detail="无法获取用户身份信息")

    row = repo.get_document_by_id(
        doc_id=doc_id, tenant_id=tenant_id, table_name=table_name)
    if not row:
        s = get_settings()
        user_table_name = getattr(s, "user_table_name", "users")
        tenant_table_name = "tenant"
        any_row = repo.get_document_with_names_by_id_any_tenant(
            doc_id=doc_id,
            table_name=table_name,
            user_table_name=user_table_name,
            tenant_table_name=tenant_table_name,
        )
        if any_row and any_row.get("uploaded_by_user_id") == current_user_id:
            row = any_row
            tenant_id = str(row.get("tenant_id") or tenant_id)
        else:
            return None

    # 检查权限
    if not _check_document_update_delete_permission(
        document=row,
        current_user_id=current_user_id,
        tenant_id=tenant_id
    ):
        raise HTTPException(status_code=403, detail="没有权限更新此文档")

    row = repo.update_document(
        doc_id=doc_id, payload=payload, tenant_id=str(row.get("tenant_id") or tenant_id), table_name=table_name)
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

    # 获取当前用户ID（从claims中获取）
    current_user_id = None
    if claims and "sub" in claims:
        # 假设 claims 中的 sub 字段包含用户ID
        try:
            current_user_id = int(claims["sub"])
        except (ValueError, TypeError):
            current_user_id = None

    # 如果没有用户ID，无法验证权限
    if current_user_id is None:
        raise HTTPException(status_code=401, detail="无法获取用户身份信息")

    table_name, _ = _get_table_and_header()

    row = repo.get_document_by_id(
        doc_id=doc_id, tenant_id=tenant_id, table_name=table_name)
    if not row:
        s = get_settings()
        user_table_name = getattr(s, "user_table_name", "users")
        tenant_table_name = "tenant"
        any_row = repo.get_document_with_names_by_id_any_tenant(
            doc_id=doc_id,
            table_name=table_name,
            user_table_name=user_table_name,
            tenant_table_name=tenant_table_name,
        )
        if any_row and any_row.get("uploaded_by_user_id") == current_user_id:
            row = any_row
            tenant_id = str(row.get("tenant_id") or tenant_id)
        else:
            return False

    # 检查权限
    if not _check_document_update_delete_permission(
        document=row,
        current_user_id=current_user_id,
        tenant_id=tenant_id
    ):
        raise HTTPException(status_code=403, detail="没有权限删除此文档")

    return repo.delete_document(doc_id=doc_id, tenant_id=str(row.get("tenant_id") or tenant_id), table_name=table_name)


def get_download_payload_service(*, doc_id: str, tenant_id: str, claims: Optional[Dict[str, Any]] = None) -> Optional[Tuple[str, str]]:
    """为下载场景组装内容与文件名。

    参数：
    - `doc_id`: 文档主键 ID。
    - `tenant_id`: 租户标识。
    - `claims`: JWT 声明（claims），用于权限校验。

    返回：
    - 二元组 `(content, filename)`；当文档不存在时返回 `None`。
      其中 `filename` 由标题派生，后缀为 `.txt`，若标题为空则默认 `document.txt`。
    """
    _ensure_authenticated(claims)
    table_name, _ = _get_table_and_header()
    row = repo.get_document_by_id(
        doc_id=doc_id, tenant_id=tenant_id, table_name=table_name)
    if not row:
        s = get_settings()
        user_table_name = getattr(s, "user_table_name", "users")
        tenant_table_name = "tenant"
        any_row = repo.get_document_with_names_by_id_any_tenant(
            doc_id=doc_id,
            table_name=table_name,
            user_table_name=user_table_name,
            tenant_table_name=tenant_table_name,
        )
        # 仅当当前用户是上传者时允许跨租户下载
        current_user_id_tmp = None
        if claims and "sub" in claims:
            try:
                current_user_id_tmp = int(claims["sub"])
            except (ValueError, TypeError):
                current_user_id_tmp = None
        if any_row and current_user_id_tmp is not None and any_row.get("uploaded_by_user_id") == current_user_id_tmp:
            row = any_row
        else:
            return None
    current_user_id = None
    if claims and "sub" in claims:
        try:
            current_user_id = int(claims["sub"])
        except (ValueError, TypeError):
            current_user_id = None
    if current_user_id is None:
        raise HTTPException(status_code=401, detail="无法获取用户身份信息")
    if not _check_document_access_permission(document=row, current_user_id=current_user_id, tenant_id=tenant_id):
        raise HTTPException(status_code=403, detail="没有权限查看此文档")
    title = (row.get("title") or "document").strip()
    content = str(row.get("content") or "")
    return content, f"{title}.txt"


def list_documents_service(
    *, page: int, per_page: int, sort: str, order: str, filters: Optional[Dict[str, Any]], type: str, tenant_id: str, claims: Optional[Dict[str, Any]] = None
) -> Tuple[list[Dict[str, Any]], int]:
    """分页查询文档列表（按租户隔离，支持模糊搜索与排序）。

    参数：
    - `page`: 页码，从 1 开始。
    - `per_page`: 每页条数。
    - `sort`: 排序字段（由仓储层映射白名单过滤，非法字段回退为 `id`）。
    - `order`: 排序方向（`ASC` 或 `DESC`）。
    - `q`: 模糊搜索关键词，匹配标题与内容。
    - `type`: 文档类型（"system" 或 "self" 或 "tenant"）。
    - `tenant_id`: 租户标识。

    返回：
    - `(rows, total)`：记录列表与总条数；其中每条记录的 `upload_time`
      字段会被统一转换为字符串。
    """
    _ensure_authenticated(claims)
    table_name, _ = _get_table_and_header()

    # 获取当前用户ID（从claims中获取）
    current_user_id = None
    if claims and "sub" in claims:
        try:
            current_user_id = int(claims["sub"])
        except (ValueError, TypeError):
            current_user_id = None

    # 如果没有用户ID，无法验证权限
    if current_user_id is None:
        raise HTTPException(status_code=401, detail="无法获取用户身份信息")

    # 根据type参数处理不同的文档查询逻辑
    if type == "system":
        s = get_settings()
        user_table_name = getattr(s, "user_table_name", "users")
        tenant_table_name = "tenant"
        rows, total = repo.list_documents_with_names(
            page=page,
            per_page=per_page,
            sort=sort,
            order=order,
            q=None,
            filters=filters,
            tenant_id="system",
            table_name=table_name,
            user_table_name=user_table_name,
            tenant_table_name=tenant_table_name,
        )
    elif type == "self":
        # type==self, 返回所有tenant_id=='default' && uploaded_by_user_id == user_id 的文档
        # 这里需要自定义查询逻辑，因为现有的list_documents不支持uploaded_by_user_id过滤
        rows, total = _list_self_documents(
            page=page,
            per_page=per_page,
            sort=sort,
            order=order,
            q=None,
            filters=filters,
            user_id=current_user_id,
            table_name=table_name,
        )
    elif type == "tenant":
        # 如果是tenant,则查找tenant_id == user的tenant_id
        # 首先获取用户信息
        user_info = user_repo.get_user_by_id(
            user_id=current_user_id,
            tenant_id=tenant_id,
            table_name="users"
        )
        if not user_info:
            raise HTTPException(status_code=404, detail="用户不存在")

        user_tenant_id = user_info.get("tenant_id", "default")
        user_role = user_info.get("role", "user")

        if user_role == "admin":
            # 如果用户是admin则可以查看全部tenant文档
            s = get_settings()
            user_table_name = getattr(s, "user_table_name", "users")
            tenant_table_name = "tenant"
            rows, total = repo.list_documents_with_names(
                page=page,
                per_page=per_page,
                sort=sort,
                order=order,
                q=None,
                filters=filters,
                tenant_id=user_tenant_id,
                table_name=table_name,
                user_table_name=user_table_name,
                tenant_table_name=tenant_table_name,
            )
        else:
            # 如果不是admin则查看user_doc_permission里面perm为admin和read的文档
            rows, total = _list_tenant_documents_with_permission(
                page=page,
                per_page=per_page,
                sort=sort,
                order=order,
                q=None,
                filters=filters,
                user_id=current_user_id,
                tenant_id=user_tenant_id,
                table_name=table_name,
            )
    else:
        raise HTTPException(
            status_code=400, detail="type 必须是 'system', 'self' 或 'tenant'")

    for r in rows:
        if r.get("upload_time") is not None:
            r["upload_time"] = str(r["upload_time"])
    return rows, total


def create_document_service(
    *,
    payload: DocumentUpload,
    tenant_id: str,
    claims: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """创建文档并返回插入后的记录，支持多种文档类型。

    说明：
    - 当未在 `payload` 中提供 `id` 时，仓储层会自动生成一个 UUID。
    - `upload_time` 由系统写入当前时间。
    - 文档状态设置为 'processing'。
    - 自动为用户创建 admin 权限记录。
    - 支持文档类型：pdf、doc/docx、md、txt、ppt/pptx、xls/xlsx、csv。

    参数：
    - `payload`: 创建所需字段字典，包含：
      - `document`: 文档内容或文件数据
      - `document_type`: 文档类型（pdf, doc, docx, md, txt, ppt, pptx, xls, xlsx, csv）
      - `title`: 文档标题
      - `tags`: 标签（可选）
      - `description`: 描述（可选）
      - `meta_https`: 元数据链接（可选）
      - `type`: 文档类型（system, self, tenant）
    - `tenant_id`: 租户标识。

    返回：
    - 新建的记录字典；其中 `upload_time` 字段会被统一转换为字符串。
    """
    _ensure_authenticated(claims)
    table_name, _ = _get_table_and_header()

    # 获取当前用户ID（从claims中获取）
    current_user_id = None
    if claims and "sub" in claims:
        try:
            current_user_id = int(claims["sub"])
        except (ValueError, TypeError):
            current_user_id = None

    # 如果没有用户ID，无法创建文档
    if current_user_id is None:
        raise HTTPException(status_code=401, detail="无法获取用户身份信息")

    # 根据type确定tenant_id
    if payload.type == "self":
        doc_tenant_id = "default"
        path = "document/default"
    elif payload.type == "system":
        doc_tenant_id = "system"
        path = "document/system"
    elif payload.type == "tenant":
        doc_tenant_id = tenant_id
        path = f"document/{tenant_id}"
    else:
        doc_tenant_id = "default"

    data = {
        "document": payload.document,
        "document_type": payload.document_type.lower(),
        "title": payload.title or "document",
        "tags": payload.tags or [],
        "description": payload.description or "",
        "meta_https": payload.meta_https or "",
        "type": payload.type or "unknown",
        "tenant_id": doc_tenant_id,
        "current_user_id": current_user_id,
    }

    data['title'] = clean_filename(data)
    logger.info(f"最终的文档名称,title: {data.get('title')}")

    # 上传文档到COS并获取URL
    save_https = upload_document_to_cos(
        data.get("document"), data.get("title"), path)
    data["save_https"] = save_https
    data["status"] = "processing"
    data["content"] = ""

    logger.info(f"创建文档 文件,已经获取cos url: {save_https}")

    # uploaded_by_user_id 统一使用当前用户ID
    data["uploaded_by_user_id"] = current_user_id

    row = repo.create_document(
        payload=data, tenant_id=doc_tenant_id, table_name=table_name)
    if row and row.get("upload_time") is not None:
        row["upload_time"] = str(row["upload_time"])
    logger.info(f"创建文档 文件,已经插入数据库: {row}")
    try:
        s = get_settings()
        perm_table = getattr(
            s, "user_doc_permission_table_name", "user_doc_permissions")
        perm_repo.create_user_doc_perm(payload={"user_id": current_user_id, "doc_id": row.get(
            "id"), "perm": "admin"}, table_name=perm_table)
    except Exception as e:
        logger.error(f"创建文档 文件,创建用户文档权限失败: {e}")
    # 发布文档解析任务到 RabbitMQ
    try:
        msg = {
            "doc_id": row.get("id"),
            "save_https": save_https,
            "document_type": data.get("document_type"),
            "tenant_id": doc_tenant_id,
        }
        # rabbitMQ:Send tag 文档解析任务
        publish_to_rabbitmq("doc_parse_tasks", msg, durable=True)
        logger.info(f"创建文档 文件,已经发布解析任务: {msg}")
    except Exception as e:
        logger.error(f"创建文档 文件,发布解析任务失败: {e}")
        # 尝试重新初始化RabbitMQ连接并重试一次
        try:
            from agentlz.core.external_services import close_all_connections
            import time
            close_all_connections()
            time.sleep(1)
            publish_to_rabbitmq("doc_parse_tasks", msg, durable=True)
            logger.info(f"创建文档 文件,重试发布解析任务成功: {msg}")
        except Exception as retry_e:
            # 更新文档状态为失败
            try:
                repo.update_document(
                    doc_id=row.get("id"),
                    payload={"status": "fail"},
                    tenant_id=doc_tenant_id,
                    table_name=table_name
                )
                logger.info(f"RabbitMQ发布任务失败,已将文档状态更新为失败: {row.get('id')}")
            except Exception as update_e:
                logger.error(f"RabbitMQ发布任务失败,更新文档状态也失败: {update_e}")
            # 可以考虑将任务保存到数据库或发送到死信队列
    return row


def process_document_from_cos_https(save_https: str, document_type: str, doc_id: str, tenant_id: str) -> str:
    """从COS下载文档并转换为Markdown格式,存入数据库document表,并切割成小文本块,存入向量数据库

    参数：
    - `save_https`: 文档在COS中的HTTPS链接。
    - `document_type`: 文档类型，用于确定转换规则。
    - `doc_id`: 文档ID，用于数据库存储。
    - `tenant_id`: 租户ID，用于确定数据库表名。

    返回：
    - 转换后的Markdown文本。
    """

    try:
        md = MarkItDown()
        ori_url = get_origin_url_from_save_https(save_https)
        logger.info(f"文档 {save_https} 转换为原始URL: {ori_url}")
        import requests
        response = requests.head(ori_url, timeout=10)
        if response.status_code != 200:
            raise Exception(f"文件无法访问，HTTP状态码: {response.status_code}")
        file_size = int(response.headers.get('Content-Length', 0))
        if file_size == 0:
            raise Exception("文件大小为0，可能文件为空或链接无效")

        # 确定文件扩展名
        forced_ext = ext_map.get(str(document_type or "").lower().strip())

        def _convert_legacy_ppt_to_markdown() -> str:
            """
            解析ppt格式
            """
            import tempfile
            import os
            import shutil
            import subprocess
            get_resp = requests.get(ori_url, stream=True, timeout=30)
            get_resp.raise_for_status()
            handle, ppt_path = tempfile.mkstemp(suffix=".ppt")
            os.close(handle)
            try:
                with open(ppt_path, "wb") as f:
                    for chunk in get_resp.iter_content(8192):
                        f.write(chunk)
                soffice = shutil.which(
                    "soffice") or shutil.which("libreoffice")
                if not soffice:
                    try:
                        from tika import parser as tika_parser
                        parsed = tika_parser.from_file(ppt_path)
                        content = (parsed.get("content") or "").strip()
                        if content:
                            return content
                    except Exception:
                        pass
                    try:
                        import textract
                        content = textract.process(ppt_path).decode(
                            "utf-8", "ignore").strip()
                        if content:
                            return content
                    except Exception:
                        pass
                    raise RuntimeError("soffice_not_found")
                outdir = tempfile.mkdtemp()
                try:
                    proc = subprocess.run(
                        [soffice, "--headless", "--convert-to",
                            "pptx", "--outdir", outdir, ppt_path],
                        capture_output=True,
                        text=True,
                        timeout=180,
                    )
                    if proc.returncode != 0:
                        raise RuntimeError(f"convert_failed: {proc.stderr}")
                    converted = None
                    for name in os.listdir(outdir):
                        if name.lower().endswith(".pptx"):
                            converted = os.path.join(outdir, name)
                            break
                    if not converted:
                        raise RuntimeError("pptx_not_generated")
                    res = md.convert_local(converted, file_extension=".pptx")
                    return res.text_content
                finally:
                    shutil.rmtree(outdir, ignore_errors=True)
            finally:
                try:
                    os.unlink(ppt_path)
                except Exception:
                    pass

        def _convert_legacy_doc_to_markdown() -> str:
            import tempfile
            import os
            import shutil
            import subprocess
            get_resp = requests.get(ori_url, stream=True, timeout=30)
            get_resp.raise_for_status()
            handle, doc_path = tempfile.mkstemp(suffix=".doc")
            os.close(handle)
            try:
                with open(doc_path, "wb") as f:
                    for chunk in get_resp.iter_content(8192):
                        f.write(chunk)
                soffice = shutil.which(
                    "soffice") or shutil.which("libreoffice")
                if not soffice:
                    try:
                        from tika import parser as tika_parser
                        parsed = tika_parser.from_file(doc_path)
                        content = (parsed.get("content") or "").strip()
                        if content:
                            return content
                    except Exception:
                        pass
                    try:
                        import textract
                        content = textract.process(doc_path).decode(
                            "utf-8", "ignore").strip()
                        if content:
                            return content
                    except Exception:
                        pass
                    raise RuntimeError("soffice_not_found")
                outdir = tempfile.mkdtemp()
                try:
                    proc = subprocess.run(
                        [soffice, "--headless", "--convert-to",
                            "docx", "--outdir", outdir, doc_path],
                        capture_output=True,
                        text=True,
                        timeout=180,
                    )
                    if proc.returncode != 0:
                        raise RuntimeError(f"convert_failed: {proc.stderr}")
                    converted = None
                    for name in os.listdir(outdir):
                        if name.lower().endswith(".docx"):
                            converted = os.path.join(outdir, name)
                            break
                    if not converted:
                        raise RuntimeError("docx_not_generated")
                    res = md.convert_local(converted, file_extension=".docx")
                    return res.text_content
                finally:
                    shutil.rmtree(outdir, ignore_errors=True)
            finally:
                try:
                    os.unlink(doc_path)
                except Exception:
                    pass

        if forced_ext == ".ppt":
            text_content = _convert_legacy_ppt_to_markdown()
        elif forced_ext == ".doc":
            text_content = _convert_legacy_doc_to_markdown()
        else:

            if forced_ext:
                result = md.convert(ori_url, file_extension=forced_ext)
            else:
                result = md.convert(ori_url)
            text_content = result.text_content

        logger.info(f"文档 {doc_id} 转换为Markdown内容，长度: {len(text_content)} 字符")
        table_name, _ = _get_table_and_header()
        repo.update_document(
            doc_id=doc_id,
            payload={"content": text_content, "status": "success"},
            tenant_id=tenant_id,
            table_name=table_name,
        )
        # 切割为Markdown块
        chunks = split_markdown_into_chunks(text_content)
        index = 0
        for chunk in chunks:
            index += 1
            logger.info(f"文档 {doc_id} 切割为Markdown块，长度: {len(chunk)} 字符")
            create_chunk_embedding_service(
                tenant_id=tenant_id,
                chunk_id=f"{doc_id}_{index}",
                doc_id=doc_id,
                content=chunk,
            )
        return ""
    except Exception as e:
        logger.error(f"文档 {doc_id} ,原始URL: {ori_url} 转换为Markdown失败: {e}")
        try:
            msg = str(e)
            if "soffice_not_found" in msg:
                logger.error(
                    "缺少 LibreOffice/soffice，安装后支持 .ppt 转换：brew install --cask libreoffice；或将 .ppt 转为 .pptx 后再上传")
        except Exception:
            pass
        table_name, _ = _get_table_and_header()
        repo.update_document(
            doc_id=doc_id,
            payload={"status": "fail"},
            tenant_id=tenant_id,
            table_name=table_name,
        )
        return ""


def list_agent_related_document_ids_service(*, agent_id: int) -> dict[str, list[str]]:
    """根据 Agent ID 获取关联文档，按租户分组返回 {tenant_id: doc_id[]}

    参数：
    - `agent_id`: Agent 主键 ID。

    返回：
    - 字典：键为租户 `tenant_id`，值为该租户下关联的文档 ID 列表（按关联记录倒序，自动去重与去空）。
    - 例如：{"default": ["doc1", "doc2"], "tenant1": ["doc3"]}
    """
    s = get_settings()
    rel_table = getattr(s, "agent_document_table_name", "agent_document")
    table_name, _ = _get_table_and_header()
    user_table_name = getattr(s, "user_table_name", "users")
    tenant_table_name = "tenant"
    rows = agdoc_repo.list_agent_documents(
        agent_id=agent_id, table_name=rel_table)
    seen: set[str] = set()
    grouped: dict[str, list[str]] = {}
    for r in rows:
        d = str(r.get("document_id") or "").strip()
        if not d or d in seen:
            continue
        seen.add(d)
        doc_row = repo.get_document_with_names_by_id_any_tenant(
            doc_id=d,
            table_name=table_name,
            user_table_name=user_table_name,
            tenant_table_name=tenant_table_name,
        )
        if not doc_row:
            continue
        tid = str(doc_row.get("tenant_id") or "")
        if not tid:
            tid = "default"
        grouped.setdefault(tid, []).append(d)
    return grouped
