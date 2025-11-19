from datetime import datetime, timedelta, timezone
from typing import Dict, Any
import jwt
from agentlz.config.settings import get_settings
from agentlz.repositories import user_repository as repo
from agentlz.schemas.user import UserCreate, UserItem
from agentlz.services import user_service

def login_service(*, username: str, password: str) -> tuple[str, UserItem]:
    s = get_settings()
    table = getattr(s, "user_table_name", "users")
    row = repo.get_user_by_username(username=username, table_name=table)
    if not row or int(row.get("disabled", 0)) == 1:
        raise ValueError("invalid_credentials")
    if str(row.get("password_hash") or "") != str(password):
        raise ValueError("invalid_credentials")
    tenant_id = str(row.get("tenant_id"))
    secret = getattr(s, "auth_jwt_secret", "dev-secret-change-me")
    alg = getattr(s, "auth_jwt_alg", "HS256")
    iss = getattr(s, "auth_jwt_issuer", "agentlz")
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=8)
    token = jwt.encode(
        {"sub": str(row["id"]), "username": username, "tenant_id": tenant_id, "iss": iss, "iat": int(now.timestamp()), "exp": int(exp.timestamp())},
        secret,
        algorithm=alg,
    )
    normalized = dict(row)
    ##在构造 UserItem 前先规范化 created_at
    ca = normalized.get("created_at")
    try:
        from datetime import datetime as _dt
        if isinstance(ca, _dt):
            normalized["created_at"] = ca.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    user = UserItem(**normalized)
    return token, user


def register_service(*, tenant_id: str, username: str, email: str, password: str) -> Dict[str, Any]:
    s = get_settings()
    table = getattr(s, "user_table_name", "users")
    exists_user = repo.get_user_by_username(username=username, table_name=table)
    if exists_user:
        raise ValueError("user_exists")
    exists_email = repo.get_user_by_email(email=email, table_name=table)
    if exists_email:
        raise ValueError("email_exists")
    payload = UserCreate(username=username, email=email, password=password)
    return user_service.create_user_service(payload=payload, tenant_id=tenant_id)