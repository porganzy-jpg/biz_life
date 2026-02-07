"""사용자 스키마"""
from pydantic import BaseModel, EmailStr
from typing import Optional

__all__ = ["UserUpdate", "UserProfileResponse", "UsageHistoryItem"]


class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None


class UserProfileResponse(BaseModel):
    id: int
    email: str
    name: str
    phone: str
    company_name: Optional[str] = None
    is_admin: bool = False
    favorites_count: int = 0
    reviews_count: int = 0
    usage_count: int = 0

    class Config:
        from_attributes = True


class UsageHistoryItem(BaseModel):
    id: int
    store_name: str
    store_brand: str
    discount_description: str
    discount_value: float
    saved_amount: float
    used_at: str

    class Config:
        from_attributes = True
