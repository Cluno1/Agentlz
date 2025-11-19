# d:\PyCharm\AgentCode\Agentlz\agentlz\app\routers\auth.py
from fastapi import APIRouter, HTTPException, Request, status
from agentlz.config.settings import get_settings
from agentlz.schemas.responses import Result
from agentlz.services.auth_service import login_service, register_service
from agentlz.schemas.auth import LoginPayload, RegisterPayload
# 注：本模块提供登录与注册接口；统一使用 Result 返回结构，需校验租户头。

router = APIRouter(prefix="/v1", tags=["auth"])


@router.post("/login", response_model=Result)
def login(payload: LoginPayload):
    try:
        token, user = login_service(username=payload.username, password=payload.password)
        return Result.ok({"token": token, "user": user})
    except ValueError as e:
        msg = str(e)
        if msg == "user_not_found":
            raise HTTPException(status_code=404, detail="用户不存在")
        if msg == "user_disabled":
            raise HTTPException(status_code=403, detail="用户已禁用")
        if msg == "invalid_password":
            raise HTTPException(status_code=401, detail="密码错误")
        raise HTTPException(status_code=400, detail="登录数据错误")




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