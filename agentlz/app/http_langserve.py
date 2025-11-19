from __future__ import annotations
from typing import Dict
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from agentlz.config.settings import get_settings
from agentlz.app.routers.users import router as users_router
from agentlz.app.routers.auth import router as auth_router
from agentlz.app.deps.auth_deps import require_auth
from agentlz.schemas.responses import Result
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

app = FastAPI()
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

@app.exception_handler(HTTPException)
async def _http_exc_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content=Result.error(message=str(getattr(exc, "detail", "")) or str(exc), code=exc.status_code).model_dump())

@app.exception_handler(RequestValidationError)
async def _validation_exc_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content=Result.error(message="Validation error", code=422, data=exc.errors()).model_dump())

@app.exception_handler(Exception)
async def _general_exc_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content=Result.error(message="Server error", code=500, data={"error": str(exc)}).model_dump())




@app.get("/v1/health", response_model=Result)
def health() -> Dict[str, str]:
    return Result.ok({"status": "ok"})