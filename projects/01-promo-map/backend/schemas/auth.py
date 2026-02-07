"""인증 스키마"""
from pydantic import BaseModel, EmailStr
from typing import Optional

__all__ = [
    "UserCreate", "UserLogin", "TokenResponse",
    "RefreshTokenRequest", "UserResponse",
]


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    phone: Optional[str] = ""
    company_code: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    phone: str = ""
    company_name: Optional[str] = None
    is_admin: bool = False

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str = ""
    token_type: str = "bearer"
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: str
