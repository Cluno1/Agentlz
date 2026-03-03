from __future__ import annotations

from typing import Any, Awaitable, Dict, Optional, Set, Tuple
import asyncio
import threading
from fastapi import WebSocket


class WSManager:
    def __init__(self) -> None:
        self._connections: Dict[WebSocket, Tuple[str, str]] = {}
        self._topics: Dict[str, Set[WebSocket]] = {}
        self._users: Dict[Tuple[str, str], Set[WebSocket]] = {}
        self._lock = asyncio.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _ensure_loop(self) -> None:
        if self._loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = None

    def submit(self, coro: Awaitable[Any]) -> Optional[asyncio.Future[Any]]:
        if self._loop is None or not self._loop.is_running():
            return None
        if threading.current_thread() is threading.main_thread():
            return asyncio.create_task(coro)
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    async def connect(self, websocket: WebSocket, tenant_id: str, user_id: str) -> None:
        self._ensure_loop()
        async with self._lock:
            self._connections[websocket] = (tenant_id, user_id)
            key = (tenant_id, user_id)
            if key not in self._users:
                self._users[key] = set()
            self._users[key].add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            info = self._connections.pop(websocket, None)
            if info:
                key = (info[0], info[1])
                sockets = self._users.get(key)
                if sockets:
                    sockets.discard(websocket)
                    if not sockets:
                        self._users.pop(key, None)
            for topic, sockets in list(self._topics.items()):
                if websocket in sockets:
                    sockets.discard(websocket)
                    if not sockets:
                        self._topics.pop(topic, None)

    async def subscribe(self, websocket: WebSocket, topic: str) -> None:
        async with self._lock:
            if topic not in self._topics:
                self._topics[topic] = set()
            self._topics[topic].add(websocket)

    async def unsubscribe(self, websocket: WebSocket, topic: str) -> None:
        async with self._lock:
            sockets = self._topics.get(topic)
            if sockets:
                sockets.discard(websocket)
                if not sockets:
                    self._topics.pop(topic, None)

    async def send(self, websocket: WebSocket, payload: Dict[str, Any]) -> None:
        try:
            await websocket.send_json(payload)
        except Exception:
            await self.disconnect(websocket)

    async def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        async with self._lock:
            sockets = list(self._topics.get(topic, set()))
        for ws in sockets:
            await self.send(ws, payload)

    async def send_to_user(self, tenant_id: str, user_id: str, payload: Dict[str, Any]) -> None:
        async with self._lock:
            sockets = list(self._users.get((tenant_id, user_id), set()))
        for ws in sockets:
            await self.send(ws, payload)

    async def broadcast_tenant(self, tenant_id: str, payload: Dict[str, Any]) -> None:
        async with self._lock:
            sockets = [ws for (tid, _), ws_set in self._users.items() if tid == tenant_id for ws in ws_set]
        for ws in sockets:
            await self.send(ws, payload)

    async def broadcast_all(self, payload: Dict[str, Any]) -> None:
        async with self._lock:
            sockets = [ws for ws_set in self._users.values() for ws in ws_set]
        for ws in sockets:
            await self.send(ws, payload)


_ws_manager: Optional[WSManager] = None


def get_ws_manager() -> WSManager:
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WSManager()
    return _ws_manager
