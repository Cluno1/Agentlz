from __future__ import annotations
from typing import Any, Dict, Optional, Tuple
from fastapi import HTTPException

from agentlz.config.settings import get_settings
from agentlz.core.logger import setup_logging
from agentlz.repositories import document_repository as repo
from agentlz.repositories import user_repository as user_repo
from agentlz.repositories import user_doc_perm_repository as perm_repo
from agentlz.schemas.document import DocumentUpload

from agentlz.services.cos_service import upload_document_to_cos
from agentlz.core.external_services import publish_to_rabbitmq

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

def _list_self_documents(
    *,
    page: int,
    per_page: int,
    sort: str,
    order: str,
    q: Optional[str],
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
    if not isinstance(claims, dict):
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
    perm_record = perm_repo.get_perm_by_user_doc(
        user_id=current_user_id, 
        doc_id=document.get("id"), 
        table_name="user_doc_permission"
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
    perm_record = perm_repo.get_perm_by_user_doc(
        user_id=current_user_id, 
        doc_id=document.get("id"), 
        table_name="user_doc_permission"
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
    """按文档 ID 查询单条记录（按租户隔离）。

    参数：
    - `doc_id`: 文档主键 ID。
    - `tenant_id`: 租户标识，用于多租户数据隔离。

    返回：
    - 文档记录字典或 `None`；其中 `upload_time` 字段会被统一转换为字符串。
    """
    _ensure_authenticated(claims)
    table_name, _ = _get_table_and_header()
    
    # 首先获取文档
    s = get_settings()
    user_table_name = getattr(s, "user_table_name", "users")
    tenant_table_name = "tenant"
    row = repo.get_document_with_names_by_id(
        doc_id=doc_id,
        tenant_id=tenant_id,
        table_name=table_name,
        user_table_name=user_table_name,
        tenant_table_name=tenant_table_name,
    )
    if not row:
        return None
    
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
    
    # 检查权限
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
    
    # 首先获取文档
    row = repo.get_document_by_id(doc_id=doc_id, tenant_id=tenant_id, table_name=table_name)
    if not row:
        return None
    
    # 检查权限
    if not _check_document_update_delete_permission(
        document=row,
        current_user_id=current_user_id,
        tenant_id=tenant_id
    ):
        raise HTTPException(status_code=403, detail="没有权限更新此文档")
        
    
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
    
    # 首先获取文档
    row = repo.get_document_by_id(doc_id=doc_id, tenant_id=tenant_id, table_name=table_name)
    if not row:
        return False
    
    # 检查权限
    if not _check_document_update_delete_permission(
        document=row,
        current_user_id=current_user_id,
        tenant_id=tenant_id
    ):
        raise HTTPException(status_code=403, detail="没有权限删除此文档")

    return repo.delete_document(doc_id=doc_id, tenant_id=tenant_id, table_name=table_name)


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
    row = repo.get_document_by_id(doc_id=doc_id, tenant_id=tenant_id, table_name=table_name)
    if not row:
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
    *, page: int, per_page: int, sort: str, order: str, q: Optional[str],type: str, tenant_id: str, claims: Optional[Dict[str, Any]] = None
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
            q=q,
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
            q=q,
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
                q=q,
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
                q=q,
                user_id=current_user_id,
                tenant_id=user_tenant_id,
                table_name=table_name,
            )
    else:
        raise HTTPException(status_code=400, detail="type 必须是 'system', 'self' 或 'tenant'")
    
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

    data = {
        "document": payload.document,
        "document_type": payload.document_type.lower(),
        "title": payload.title or "document",
        "tags": payload.tags or [],
        "description": payload.description or "",
        "meta_https": payload.meta_https or "",
        "type": payload.type or "self",
        "tenant_id": tenant_id,
        "current_user_id": current_user_id,
    }
    
    # 验证文档类型
    supported_types = ["pdf", "doc", "docx", "md", "txt", "ppt", "pptx", "xls", "xlsx", "csv"]
    if data.get("document_type") not in supported_types:
        raise HTTPException(status_code=400, detail=f"不支持的文档类型。支持类型：{', '.join(supported_types)}")
    
    suffix_map = {
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
    
    filename = f"{data.get('title')}{suffix_map.get(data.get('document_type'), '')}"
    
    # 上传文档到COS并获取URL
    save_https = upload_document_to_cos(data.get("document"), filename)
    data["meta_https"] = save_https
    data["content"] = ""

    
    logger.info(f"创建文档 文件,已经获取cos url: {data}")

    
    # uploaded_by_user_id 统一使用当前用户ID
    data["uploaded_by_user_id"] = current_user_id

    row = repo.create_document(payload=data, tenant_id=tenant_id, table_name=table_name)
    if row and row.get("upload_time") is not None:
        row["upload_time"] = str(row["upload_time"])
    
    # 发布文档解析任务到 RabbitMQ
    try:
        msg = {
            "doc_id": row.get("id"),
            "tenant_id": tenant_id,
            "save_https": save_https,
            "document_type": data.get("document_type"),
            "uploaded_by_user_id": current_user_id,
        }
        publish_to_rabbitmq("doc_parse_tasks", msg, durable=True)
        logger.info(f"创建文档 文件,已经发布解析任务: {msg}")
    except Exception as e:
        logger.error(f"创建文档 文件,发布解析任务失败: {e}")
    try:
        s = get_settings()
        perm_table = getattr(s, "user_doc_permission_table_name", "user_doc_permissions")
        perm_repo.create_user_doc_perm(payload={"user_id": current_user_id, "doc_id": row.get("id"), "perm": "admin"}, table_name=perm_table)
    except Exception as e:
        logger.error(f"创建文档 文件,创建用户文档权限失败: {e}")
    return row
    

