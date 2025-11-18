# d:\PyCharm\AgentCode\Agentlz\agentlz\app\deps\auth.py
from typing import Dict, Any
from fastapi import Header, HTTPException
from pydantic.types import T
from agentlz.config.settings import get_settings
import jwt
from datetime import datetime, timezone

def require_auth(authorization: str = Header(None)) -> Dict[str, Any]:
    s = get_settings()
    secret = getattr(s, "auth_jwt_secret", "dev-secret-change-me")
    alg = getattr(s, "auth_jwt_alg", "HS256")
    iss = getattr(s, "auth_jwt_issuer", "agentlz")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization")
    token = authorization.split(" ", 1)[1]
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=[alg],
            options={"require": ["iss", "sub"]}
        )
        if claims.get("iss") != iss:
            raise HTTPException(status_code=401, detail="Invalid token issuer")
        return claims
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidSignatureError:
        raise HTTPException(status_code=401, detail="Invalid signature")
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")