from __future__ import annotations
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from fastapi.responses import Response

from agentlz.schemas.document import DocumentUpdate
from agentlz.schemas.responses import Result
from agentlz.services import document_service
from agentlz.app.deps.auth_deps import require_auth, require_tenant_id, require_admin


router = APIRouter(prefix="/v1", tags=["documents"])


@router.get("/rag/{doc_id}", response_model=Result)
def get_document(doc_id: str, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    tenant_id = require_tenant_id(request)
    row = document_service.get_document_service(doc_id=doc_id, tenant_id=tenant_id, claims=claims)
    if not row:
        raise HTTPException(status_code=404, detail="文档不存在")
    return Result.ok(row)


@router.put("/rag/{doc_id}", response_model=Result)
def update_document(doc_id: str, payload: DocumentUpdate, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    tenant_id = require_tenant_id(request)
    require_admin(claims, tenant_id)
    row = document_service.update_document_service(doc_id=doc_id, payload=payload.model_dump(exclude_none=True), tenant_id=tenant_id, claims=claims)
    if not row:
        raise HTTPException(status_code=404, detail="文档不存在")
    return Result.ok(row)


@router.delete("/rag/{doc_id}", response_model=Result)
def delete_document(doc_id: str, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
    tenant_id = require_tenant_id(request)
    require_admin(claims, tenant_id)
    ok = document_service.delete_document_service(doc_id=doc_id, tenant_id=tenant_id, claims=claims)
    if not ok:
        raise HTTPException(status_code=404, detail="文档不存在")
    return Result.ok({})


@router.get("/rag/{doc_id}/download")
def download_document(doc_id: str, request: Request, claims: Dict[str, Any] = Depends(require_auth)):
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
    q: Optional[str] = Query(None, description="搜索关键词"),
    type: str = Query("self", regex="^(system|self|tenant)$", description="文档类型")
):
    """分页查询文档列表（支持多类型查询）"""
    tenant_id = require_tenant_id(request)
    rows, total = document_service.list_documents_service(
        page=page,
        per_page=per_page,
        sort=sort,
        order=order,
        q=q,
        type=type,
        tenant_id=tenant_id,
        claims=claims
    )
    return Result.ok(data={"rows": rows, "total": total})


@router.post("/rag", response_model=Result)
def create_document(
    request: Request,
    payload: Dict[str, Any],
    claims: Dict[str, Any] = Depends(require_auth)
):
    """创建新文档（需要管理员权限）"""
    tenant_id = require_tenant_id(request)
    row = document_service.create_document_service(
        payload=payload,
        tenant_id=tenant_id,
        claims=claims
    )
    return Result.ok(data=row)