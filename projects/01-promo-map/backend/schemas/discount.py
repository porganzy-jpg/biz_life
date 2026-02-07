"""할인 스키마"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

__all__ = [
    "DiscountResponse", "DiscountCreateRequest", "DiscountUpdateRequest",
]


class DiscountResponse(BaseModel):
    id: int
    store_id: int
    company_id: int
    discount_type: str
    discount_value: float
    description: str
    min_purchase: int = 0
    max_discount: int = 0
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    is_active: bool = True
    store_name: Optional[str] = None
    store_brand: Optional[str] = None
    company_name: Optional[str] = None

    class Config:
        from_attributes = True


class DiscountCreateRequest(BaseModel):
    store_id: int
    company_id: int
    discount_type: str = "percent"
    discount_value: float
    description: str = ""
    min_purchase: int = 0
    max_discount: int = 0
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None


class DiscountUpdateRequest(BaseModel):
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    description: Optional[str] = None
    min_purchase: Optional[int] = None
    max_discount: Optional[int] = None
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    is_active: Optional[bool] = None
