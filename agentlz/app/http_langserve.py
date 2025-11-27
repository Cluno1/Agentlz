from __future__ import annotations
from typing import Dict
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from agentlz.config.settings import get_settings
from agentlz.app.routers.users import router as users_router
from agentlz.app.routers.auth import router as auth_router
from agentlz.app.routers.document import router as document_router
from agentlz.app.deps.auth_deps import require_auth
from agentlz.schemas.responses import Result
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from agentlz.core.external_services import close_all_connections
from agentlz.services.mq_service import start_mq_service, stop_mq_service
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动MQ服务作为守护线程
    try:
        start_mq_service()
        logger.info("MQ服务已启动为守护线程")
    except Exception as e:
        logger.error(f"启动MQ服务失败: {e}")
        # 不阻止应用启动，只是记录错误
    
    yield
    
    # 关闭时停止MQ服务
    try:
        stop_mq_service()
        logger.info("MQ服务已停止")
    except Exception as e:
        logger.error(f"停止MQ服务时出错: {e}")
    
    # 关闭时清理所有外部服务连接
    try:
        close_all_connections()
        logger.info("所有外部服务连接已关闭")
    except Exception as e:
        logger.error(f"关闭外部服务连接时出错: {e}")

app = FastAPI(lifespan=lifespan)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)
app.include_router(auth_router)
app.include_router(users_router, dependencies=[Depends(require_auth)])
app.include_router(document_router, dependencies=[Depends(require_auth)])

@app.exception_handler(HTTPException)
async def _http_exc_handler(request: Request, exc: HTTPException):
    msg = str(getattr(exc, "detail", "")) or str(exc)
    return JSONResponse(
        status_code=exc.status_code,
        content=Result.error(message=msg, code=exc.status_code, data={}).model_dump(),
    )

@app.exception_handler(RequestValidationError)
async def _validation_exc_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=Result.error(message="参数校验错误", code=422, data={"errors": exc.errors(), "path": request.url.path}).model_dump(),
    )

@app.exception_handler(Exception)
async def _general_exc_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=Result.error(message="服务器内部错误", code=500, data={"error": str(exc), "path": request.url.path}).model_dump(),
    )




@app.get("/v1/health", response_model=Result)
def health() -> Dict[str, str]:
    return Result.ok({"status": "ok"})

@app.get("/v1/health/rabbitmq", response_model=Result)
def health_rabbitmq() -> Dict[str, Any]:
    """RabbitMQ健康检查端点"""
    try:
        from agentlz.core.external_services import test_rabbitmq_connection
        result = test_rabbitmq_connection()
        if result["connection_status"] and result["channel_status"]:
            return Result.ok(result)
        else:
            return Result.error(
                message=f"RabbitMQ连接异常: {result['message']}", 
                code=503, 
                data=result
            )
    except Exception as e:
        logger.error(f"RabbitMQ健康检查失败: {e}")
        return Result.error(
            message=f"RabbitMQ健康检查失败: {str(e)}", 
            code=500, 
            data={}
        )
