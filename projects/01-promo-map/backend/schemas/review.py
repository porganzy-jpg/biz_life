"""리뷰 스키마"""
from pydantic import BaseModel, field_validator
from typing import Optional

__all__ = ["ReviewCreateRequest", "ReviewResponse"]


class ReviewCreateRequest(BaseModel):
    store_id: int
    rating: int
    content: str = ""

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v):
        if v < 1 or v > 5:
            raise ValueError("Rating must be between 1 and 5")
        return v


class ReviewResponse(BaseModel):
    id: int
    user_id: int
    user_name: str
    store_id: int
    rating: int
    content: str
    created_at: str

    class Config:
        from_attributes = True
