from __future__ import annotations
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Request, status, Depends
from fastapi.responses import Response

from agentlz.schemas.document import DocumentItem, DocumentUpdate
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