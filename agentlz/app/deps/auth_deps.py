# d:\PyCharm\AgentCode\Agentlz\agentlz\app\deps\auth.py
from typing import Dict, Any, Optional
from fastapi import Header, HTTPException, Request
from pydantic.types import T
from agentlz.config.settings import get_settings
import jwt
from agentlz.services import user_service

def require_auth(authorization: str = Header(None)) -> Dict[str, Any]:
    """校验并解析 Authorization 头中的 JWT 令牌。

    参数：
    - `authorization`: Authorization 头，格式为 "Bearer <token>"

    返回：
    - 解析后的 JWT 声明（claims）

    异常：
    - `HTTPException(401)`: 缺少或非法的 Authorization 头
    - `HTTPException(401)`: 令牌已过期
    - `HTTPException(401)`: 令牌签名无效
    - `HTTPException(401)`: 令牌发行者不匹配
    - `HTTPException(401)`: 其他 JWT 错误
    """
    s = get_settings()
    secret = getattr(s, "auth_jwt_secret", "dev-secret-change-me")
    alg = getattr(s, "auth_jwt_alg", "HS256")
    iss = getattr(s, "auth_jwt_issuer", "agentlz")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="缺少或非法的 Authorization 头")
    token = authorization.split(" ", 1)[1]
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=[alg],
            options={"require": ["iss", "sub"]}
        )
        if claims.get("iss") != iss:
            raise HTTPException(status_code=401, detail="令牌发行者不匹配")
        return claims
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="令牌已过期")
    except jwt.InvalidSignatureError:
        raise HTTPException(status_code=401, detail="令牌签名无效")
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"令牌无效：{e}")


def require_tenant_id(request: Request) -> str:
    """从请求头中提取租户 ID。

    参数：
    - `request`: FastAPI 请求对象

    返回：
    - 提取到的租户 ID

    异常：
    - `HTTPException(400)`: 缺少租户头或租户 ID 为空
    """
    s = get_settings()
    tenant_header = getattr(s, "tenant_id_header", "X-Tenant-ID")
    tenant_id = request.headers.get(tenant_header)
    if not tenant_id:
        raise HTTPException(status_code=400, detail=f"Missing tenant header: {tenant_header}")
    return tenant_id


def _parse_sub_id(claims: Dict[str, Any]) -> Optional[int]:
    """从 JWT 声明中解析用户 ID（sub）。

    参数：
    - `claims`: JWT 声明（claims）

    返回：
    - 解析后的用户 ID（整数），如果解析失败则返回 None
    """
    sub = claims.get("sub")
    try:
        return int(sub) if sub is not None else None
    except Exception:
        return None


def _get_current_user(claims: Dict[str, Any], tenant_id: str) -> Optional[Dict[str, Any]]:
    """根据 JWT 声明和租户 ID 查询当前用户。

    参数：
    - `claims`: JWT 声明（claims）
    - `tenant_id`: 租户 ID

    返回：
    - 当前用户的字典表示，如果查询失败则返回 None
    """
    sub_id = _parse_sub_id(claims)
    return user_service.get_user_service(user_id=sub_id, tenant_id=tenant_id) if sub_id is not None else None


def require_admin(claims: Dict[str, Any], tenant_id: str) -> None:
    """校验当前用户是否为管理员角色。

    参数：
    - `claims`: JWT 声明（claims）
    - `tenant_id`: 租户 ID

    异常：
    - `HTTPException(403)`: 当前用户不是管理员角色
    """

    current = _get_current_user(claims, tenant_id)
    if not current or (current.get("role") != "admin"):
        raise HTTPException(status_code=403, detail="无权限：需要管理员角色")


def require_admin_or_self(target_user_id: int, claims: Dict[str, Any], tenant_id: str) -> None:
    """校验当前用户是否为管理员角色或目标用户本人。

    参数：
    - `target_user_id`: 目标用户 ID
    - `claims`: JWT 声明（claims）
    - `tenant_id`: 租户 ID

    异常：
    - `HTTPException(403)`: 当前用户不是管理员角色或目标用户本人
    """
    if str(target_user_id) == str(claims.get("sub")):
        return
    current = _get_current_user(claims, tenant_id)
    if not current or (current.get("role") != "admin"):
        raise HTTPException(status_code=403, detail="无权限：仅管理员或本人可操作")