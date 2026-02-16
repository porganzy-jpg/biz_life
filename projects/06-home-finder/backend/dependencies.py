"""
HomeFinder - FastAPI 의존성 (DI)
"""
from fastapi import Depends, Query
from sqlalchemy.orm import Session
from database import get_db


def get_pagination(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
):
    return {"page": page, "size": size, "offset": (page - 1) * size}
