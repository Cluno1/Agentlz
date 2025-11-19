from __future__ import annotations

from pydantic import BaseModel, EmailStr

class LoginPayload(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    token: str

class RegisterPayload(BaseModel):
    username: str
    email: EmailStr
    password: str