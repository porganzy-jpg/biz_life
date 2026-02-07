"""즐겨찾기 스키마"""
from pydantic import BaseModel

__all__ = ["FavoriteRequest", "FavoriteResponse"]


class FavoriteRequest(BaseModel):
    store_id: int


class FavoriteResponse(BaseModel):
    id: int
    store_id: int
    store_name: str
    store_brand: str
    store_category: str
    icon_color: str
    icon_letter: str

    class Config:
        from_attributes = True
