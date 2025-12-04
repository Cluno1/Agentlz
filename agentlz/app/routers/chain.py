from __future__ import annotations
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, Request
from starlette.responses import StreamingResponse
from agentlz.app.deps.auth_deps import require_auth, require_tenant_id
from agentlz.services.chain.chain_service import stream_chain_generator

router = APIRouter(prefix="/v1", tags=["chain"])

@router.get("/chat")
async def chain_stream(user_input: str, request: Request, claims: Dict[str, Any] = Depends(require_auth), max_steps: Optional[int] = None):
    tenant_id = require_tenant_id(request)
    gen = stream_chain_generator(user_input=user_input, tenant_id=tenant_id, claims=claims, max_steps=max_steps)
    headers = {"Content-Type": "text/event-stream", "Cache-Control": "no-cache", "Connection": "keep-alive"}
    return StreamingResponse(gen, media_type="text/event-stream", headers=headers)
