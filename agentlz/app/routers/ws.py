from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from agentlz.app.deps.auth_deps import require_auth
from agentlz.core.ws_manager import get_ws_manager

router = APIRouter(prefix="/v1", tags=["ws"])


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    manager = get_ws_manager()
    tenant_id = ""
    user_id = ""
    try:
        first: Dict[str, Any] = await websocket.receive_json()
        if first.get("type") != "auth":
            await websocket.close(code=4401)
            return
        token = str(first.get("token") or "")
        if not token:
            await websocket.close(code=4401)
            return
        try:
            claims = require_auth(authorization=f"Bearer {token}")
        except HTTPException:
            await websocket.close(code=4401)
            return
        tenant_id = str(first.get("tenant_id") or claims.get("tenant_id") or "")
        if not tenant_id:
            await websocket.close(code=4403)
            return
        token_tenant = str(claims.get("tenant_id") or "")
        if token_tenant and token_tenant != tenant_id:
            await websocket.close(code=4403)
            return
        user_id = str(claims.get("sub") or "")
        if not user_id:
            await websocket.close(code=4401)
            return
        await manager.connect(websocket, tenant_id=tenant_id, user_id=user_id)
        await websocket.send_json({"type": "auth.ok", "tenant_id": tenant_id, "user_id": user_id})
        while True:
            msg: Dict[str, Any] = await websocket.receive_json()
            mtype = str(msg.get("type") or "")
            if mtype == "subscribe":
                topic = str(msg.get("topic") or "")
                if topic:
                    await manager.subscribe(websocket, topic)
                    await websocket.send_json({"type": "subscribed", "topic": topic})
            elif mtype == "unsubscribe":
                topic = str(msg.get("topic") or "")
                if topic:
                    await manager.unsubscribe(websocket, topic)
                    await websocket.send_json({"type": "unsubscribed", "topic": topic})
            elif mtype == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await manager.disconnect(websocket)
