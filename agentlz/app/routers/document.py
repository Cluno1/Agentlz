from __future__ import annotations
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request, Depends, Query, File, Form, UploadFile
from fastapi.responses import Response
from agentlz.core.logger import setup_logging
from agentlz.schemas.document import DocumentUpdate, DocumentUpload, DocumentQuery, ChunkStrategyPayload
from agentlz.schemas.responses import Result
from agentlz.services.rag import document_service
from agentlz.services.rag import chunk_embeddings_service
from agentlz.app.deps.auth_deps import require_auth, require_tenant_id, require_admin

logger = setup_logging()

router = APIRouter(prefix="/v1", tags=["documents"])


@router.get("/rag/{doc_id}", response_model=Result)
def get_document(doc_id: str, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    logger.info(f"get_document: doc_id={doc_id}")
    tenant_id = require_tenant_id(request)
    row = document_service.get_document_service(doc_id=doc_id, tenant_id=tenant_id, claims=claims)
    if not row:
        raise HTTPException(status_code=404, detail="文档不存在")
    return Result.ok(row)


@router.put("/rag/{doc_id}", response_model=Result)
def update_document(doc_id: str, payload: DocumentUpdate, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    logger.info(f"update_document: doc_id={doc_id}")
    tenant_id = require_tenant_id(request)
    row = document_service.update_document_service(doc_id=doc_id, payload=payload.model_dump(exclude_none=True), tenant_id=tenant_id, claims=claims)
    if not row:
        raise HTTPException(status_code=404, detail="文档不存在")
    return Result.ok(row)


@router.delete("/rag/{doc_id}", response_model=Result)
def delete_document(doc_id: str, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    logger.info(f"delete_document: doc_id={doc_id}")
    tenant_id = require_tenant_id(request)
    require_admin(claims, tenant_id)
    ok = document_service.delete_document_service(doc_id=doc_id, tenant_id=tenant_id, claims=claims)
    if not ok:
        raise HTTPException(status_code=404, detail="文档不存在")
    return Result.ok({})


@router.get("/rag/{doc_id}/download")
def download_document(doc_id: str, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    logger.info(f"download_document: doc_id={doc_id}")
    tenant_id = require_tenant_id(request)
    payload = document_service.get_download_payload_service(doc_id=doc_id, tenant_id=tenant_id, claims=claims)
    if not payload:
        raise HTTPException(status_code=404, detail="文档不存在")
    content, filename = payload
    return Response(content, media_type="text/plain", headers={"Content-Disposition": f"attachment; filename=\"{filename}\""})


@router.get("/rag", response_model=Result)
def list_documents(
    request: Request,
    claims: Dict[str, Any] = Depends(require_auth),
    page: int = Query(1, ge=1, description="页码，从1开始"),
    per_page: int = Query(10, ge=1, le=100, description="每页条数"),
    sort: str = Query("id", description="排序字段"),
    order: str = Query("DESC", regex="^(ASC|DESC)$", description="排序方向"),
    type: str = Query("self", regex="^(system|self|tenant)$", description="文档类型"),
    filters: DocumentQuery = Depends()
):
    """分页查询文档列表（支持多类型查询）"""
    fdict = filters.model_dump(exclude_none=True)
    logger.info(f"list_documents: page={page}, per_page={per_page}, sort={sort}, order={order}, type={type}, filters={fdict}")
    tenant_id = require_tenant_id(request)
    rows, total = document_service.list_documents_service(
        page=page,
        per_page=per_page,
        sort=sort,
        order=order,
        filters=fdict,
        type=type,
        tenant_id=tenant_id,
        claims=claims
    )
    return Result.ok(data={"rows": rows, "total": total})


@router.post("/rag", response_model=Result)
def create_document(
    request: Request,
    document: UploadFile = File(...),
    document_type: str = Form(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    meta_https: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),  # JSON字符串格式
    type: str = Form("self"),
    strategy: Optional[str] = Form(None),
    claims: Dict[str, Any] = Depends(require_auth)
):
    """创建新文档（需要管理员权限）
    
    参数
    - document: 上传的文件
    - document_type: 文档类型（pdf, doc, docx, md, txt, ppt, pptx, xls, xlsx, csv）
    - title: 文档标题
    - description: 描述（可选）
    - meta_https: 元数据链接（可选）
    - tags: 标签，JSON字符串格式（可选）
    - type: 文档类型（system, self, tenant）
    - strategy: 切割策略数组（字符串形式，如 ["0","1"] 或 [0,1]）
    """
    logger.info(f"create_document: title={title}, type={type}, filename={document.filename}")
    
    # 验证 type 字段
    if type not in ["system", "self", "tenant"]:
        raise HTTPException(status_code=400, detail="type 字段必须是 system、self 或 tenant")
    
    # 处理tags字段
    import json
    tags_list = None
    if tags:
        try:
            tags_list = json.loads(tags)
            if not isinstance(tags_list, list):
                raise HTTPException(status_code=400, detail="tags 必须是数组格式")
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="tags 格式错误，必须是有效的JSON数组")
    
    # 读取文件内容
    try:
        file_content = document.file.read()
        logger.info(f"文件读取成功: {document.filename}, 大小: {len(file_content)} bytes")
    except Exception as e:
        logger.error(f"文件读取失败: {e}")
        raise HTTPException(status_code=400, detail=f"文件读取失败: {str(e)}")
    
    # 创建payload对象（strategy 支持JSON数组字符串，如 ["0","1"] 或 [0,1]）
    import json
    strategy_list = None
    if strategy:
        try:
            strategy_list = json.loads(strategy)
            if not isinstance(strategy_list, list):
                raise HTTPException(status_code=400, detail="strategy 必须是数组格式")
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="strategy 格式错误，必须是有效的JSON数组")

    payload = DocumentUpload(
        document=file_content,
        document_type=document_type,
        title=title,
        description=description,
        meta_https=meta_https,
        tags=tags_list,
        type=type,
        strategy=strategy_list
    )
    
    tenant_id = require_tenant_id(request)
    row = document_service.create_document_service(
        payload=payload,
        tenant_id=tenant_id,
        claims=claims
    )
    return Result.ok(data=row)

@router.put("/rag/{doc_id}/chunk", response_model=Result)
def publish_document_chunk(
    doc_id: str,
    payload: ChunkStrategyPayload,
    request: Request,
    claims: Dict[str, Any] = Depends(require_auth)
):
    """为指定文档发布分块解析任务（RabbitMQ）
    
    输入：
    - strategy: 策略列表（如 [1,2,3]）
    
    说明：
    - 鉴权复用 document_service.get_document_service 内部逻辑
    - 每个策略将发布一条解析任务到队列 doc_parse_tasks
    """
    tenant_id = require_tenant_id(request)
    ret = document_service.publish_document_chunk_tasks_service(
        doc_id=doc_id,
        strategies=payload.strategy,
        tenant_id=tenant_id,
        claims=claims
    )
    return Result.ok(data=ret)

@router.get("/rag/{doc_id}/strategy", response_model=Result)
def list_document_strategies(
    doc_id: str,
    request: Request,
    claims: Dict[str, Any] = Depends(require_auth),
    limit: int = Query(20, ge=1, le=200, description="每页数量上限"),
    offset: int = Query(0, ge=0, description="偏移量"),
    include_vector: bool = Query(False, description="是否返回向量字段")
):
    """列出指定文档的所有切割策略的分块列表（分页）
    
    返回结构：
    - [{doc_id, tenant_id, "0":[{index, chunk_id, content, created_at, embedding?}], "1":[...], ...}]
    """
    logger.info(f"list_document_strategies: doc_id={doc_id}, limit={limit}, offset={offset}, include_vector={include_vector}")
    tenant_id = require_tenant_id(request)
    # 使用文档服务进行权限校验（内部已包含鉴权逻辑）
    row = document_service.get_document_service(doc_id=doc_id, tenant_id=tenant_id, claims=claims)
    if not row:
        raise HTTPException(status_code=404, detail="文档不存在")
    # 获取聚合后的分块列表（不传 strategy，返回所有策略）
    data = chunk_embeddings_service.list_chunk_embeddings_service(
        tenant_id=tenant_id,
        doc_id=doc_id,
        strategy=None,
        limit=limit,
        offset=offset,
        include_vector=include_vector
    )
    return Result.ok(data=data)


@router.get("/rag/{doc_id}/strategy/{strategy}", response_model=Result)
def list_document_strategy_chunks(
    doc_id: str,
    strategy: str,
    request: Request,
    claims: Dict[str, Any] = Depends(require_auth),
    limit: int = Query(20, ge=1, le=200, description="每页数量上限"),
    offset: int = Query(0, ge=0, description="偏移量"),
    include_vector: bool = Query(False, description="是否返回向量字段")
):
    """列出指定文档在特定策略下的分块列表（分页）
    
    返回结构：
    - [{doc_id, tenant_id, "<strategy>":[{index, chunk_id, content, created_at, embedding?}]}]
    """
    logger.info(f"list_document_strategy_chunks: doc_id={doc_id}, strategy={strategy}, limit={limit}, offset={offset}, include_vector={include_vector}")
    tenant_id = require_tenant_id(request)
    # 使用文档服务进行权限校验（内部已包含鉴权逻辑）
    row = document_service.get_document_service(doc_id=doc_id, tenant_id=tenant_id, claims=claims)
    if not row:
        raise HTTPException(status_code=404, detail="文档不存在")
    # 获取聚合后的分块列表（仅返回指定策略分组）
    data = chunk_embeddings_service.list_chunk_embeddings_service(
        tenant_id=tenant_id,
        doc_id=doc_id,
        strategy=strategy,
        limit=limit,
        offset=offset,
        include_vector=include_vector
    )
    return Result.ok(data=data)
