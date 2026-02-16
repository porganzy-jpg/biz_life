"""페이지네이션 응답 스키마"""
from typing import Generic, TypeVar, List

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """페이지네이션이 포함된 제네릭 응답"""

    items: List[T] = Field(description="결과 목록")
    total: int = Field(description="전체 결과 수")
    page: int = Field(ge=1, description="현재 페이지 번호")
    page_size: int = Field(ge=1, le=100, description="페이지당 항목 수")
    total_pages: int = Field(description="전체 페이지 수")
    has_next: bool = Field(description="다음 페이지 존재 여부")
    has_prev: bool = Field(description="이전 페이지 존재 여부")
