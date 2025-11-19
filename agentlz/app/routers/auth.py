# d:\PyCharm\AgentCode\Agentlz\agentlz\app\routers\auth.py
from fastapi import APIRouter, HTTPException, Request, status
from agentlz.config.settings import get_settings
from agentlz.schemas.responses import Result
from agentlz.services.auth_service import login_service, register_service
from agentlz.schemas.auth import LoginPayload, RegisterPayload
# 注：本模块提供登录与注册接口；统一使用 Result 返回结构，需校验租户头。

router = APIRouter(prefix="/v1", tags=["auth"])


@router.post("/login", response_model=Result)
def login(payload: LoginPayload, request: Request):
    # 登录：校验用户名与密码，签发 JWT（含 sub/username/tenant_id/iss/iat/exp）
    s = get_settings()
    tenant_header = getattr(s, "tenant_id_header", "X-Tenant-ID")
    tenant_id = request.headers.get(tenant_header)
    if not tenant_id:
        raise HTTPException(status_code=400, detail=f"Missing tenant header: {tenant_header}")
    try:
        token = login_service(tenant_id=tenant_id, username=payload.username, password=payload.password)
        return Result.ok({"token": token})
    except ValueError:
        raise HTTPException(status_code=401, detail="用户名或密码错误")




@router.post("/register", response_model=Result, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterPayload, request: Request):
    # 注册：校验租户头与用户名/邮箱重复，创建用户并返回用户信息
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
            raise HTTPException(status_code=409, detail="用户名已存在")
        if str(e) == "email_exists":
            raise HTTPException(status_code=409, detail="邮箱已存在")
        raise