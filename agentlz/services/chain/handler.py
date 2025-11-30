from __future__ import annotations

from typing import Optional, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .chain_service import ChainContext


class Handler:
    """责任链节点基类

    提供统一的 `handle` 执行入口与 `next` 跳转接口，子类按需覆盖。
    """

    def __init__(self):
        self._next: Optional[Handler] = None

    def set_next(self, h: "Handler") -> "Handler":
        """设置下一节点并返回该节点，便于链式拼接"""
        self._next = h
        return h

    async def handle(self, ctx: "ChainContext") -> "ChainContext":
        """执行当前节点逻辑，默认透传到下一节点"""
        if self._next:
            return await self._next.handle(ctx)
        return ctx

    def next(self, ctx: "ChainContext") -> Optional["Handler"]:
        """返回下一节点（默认按初始化顺序），子类可根据上下文动态跳转"""
        return self._next

    def send_sse(self, ctx: "ChainContext", evt: str, payload: Any) -> None:
        """
        统一的 SSE 发送入口：
        - 从上下文中取出发射器 `ctx.sse_emitter`
        - 按事件类型 `evt` 推送负载 `payload`
        - 在步骤中调用，服务层负责序列化与输送到 SSE 流
        """
        emit = getattr(ctx, "sse_emitter", None)
        if not emit:
            return
        try:
            # 将事件与负载交给服务层注册的发射器，进入队列等待消费
            emit(evt, payload)
        except Exception:
            # 发送失败不影响主流程，静默吞掉异常
            pass
