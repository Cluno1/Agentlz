# d:\PyCharm\AgentCode\Agentlz\agentlz\app\routers\auth.py
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from agentlz.config.settings import get_settings
from agentlz.schemas.responses import Result
from agentlz.services.auth_service import login_service, register_service

router = APIRouter(prefix="/v1", tags=["auth"])

class LoginPayload(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    token: str

@router.post("/login", response_model=Result)
def login(payload: LoginPayload, request: Request):
    s = get_settings()
    tenant_header = getattr(s, "tenant_id_header", "X-Tenant-ID")
    tenant_id = request.headers.get(tenant_header)
    if not tenant_id:
        raise HTTPException(status_code=400, detail=f"Missing tenant header: {tenant_header}")
    try:
        token = login_service(tenant_id=tenant_id, username=payload.username, password=payload.password)
        return Result.ok({"token": token})
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid credentials")


class RegisterPayload(BaseModel):
    username: str
    email: Optional[str] = None
    password: str


@router.post("/register", response_model=Result, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterPayload, request: Request):
    s = get_settings()
    tenant_header = getattr(s, "tenant_id_header", "X-Tenant-ID")
    tenant_id = request.headers.get(tenant_header)
    if not tenant_id:
        raise HTTPException(status_code=400, detail=f"Missing tenant header: {tenant_header}")
    try:
        row = register_service(tenant_id=tenant_id, username=payload.username, email=payload.email, password=payload.password)
        return Result.ok(row)
    except ValueError as e:
        if str(e) == "user_exists":
            raise HTTPException(status_code=409, detail="User already exists")
        if str(e) == "email_exists":
            raise HTTPException(status_code=409, detail="Email already exists")
        raise