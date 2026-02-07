"""매장 스키마"""
from pydantic import BaseModel
from typing import Optional, List

__all__ = [
    "StoreResponse", "StoreDetailResponse", "StoreListResponse",
    "NearbyStoreResponse", "StoreCreateRequest", "StoreUpdateRequest",
]


class DiscountBrief(BaseModel):
    id: int
    type: str
    value: float
    description: str


class StoreResponse(BaseModel):
    id: int
    name: str
    brand: str
    category: str
    address: str
    latitude: float
    longitude: float
    phone: str = ""
    icon_color: str
    icon_letter: str
    distance_m: Optional[float] = None
    discounts: List[DiscountBrief] = []

    class Config:
        from_attributes = True


class StoreDetailResponse(StoreResponse):
    reviews_count: int = 0
    avg_rating: Optional[float] = None
    is_favorited: bool = False


class StoreListResponse(BaseModel):
    count: int
    stores: List[StoreResponse]


class NearbyStoreResponse(BaseModel):
    count: int
    stores: List[StoreResponse]


class StoreCreateRequest(BaseModel):
    name: str
    brand: str
    category: str = "general"
    address: str = ""
    latitude: float
    longitude: float
    phone: str = ""
    icon_color: str = "#FF6B35"
    icon_letter: str = "S"


class StoreUpdateRequest(BaseModel):
    name: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone: Optional[str] = None
    icon_color: Optional[str] = None
    icon_letter: Optional[str] = None
    is_active: Optional[bool] = None
