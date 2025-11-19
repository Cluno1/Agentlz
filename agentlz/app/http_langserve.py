from __future__ import annotations
from typing import Dict
from fastapi import FastAPI, Depends, Request, HTTPException
from agentlz.app.routers.users import router as users_router
from agentlz.app.routers.auth import router as auth_router
from agentlz.app.deps.auth_deps import require_auth
from agentlz.schemas.responses import Result
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

app = FastAPI()
app.include_router(auth_router)
app.include_router(users_router, dependencies=[Depends(require_auth)])

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