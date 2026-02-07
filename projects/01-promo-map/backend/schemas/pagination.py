"""페이지네이션 스키마"""
from pydantic import BaseModel
from typing import Generic, TypeVar, List, Optional

__all__ = ["PaginationParams", "PaginatedResponse"]

T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = 1
    size: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    size: int
    pages: int
