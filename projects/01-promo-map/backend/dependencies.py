"""
PromoMap - FastAPI 의존성 (DI)
"""
import sys
import os

_shared_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "shared")
if _shared_path not in sys.path:
    sys.path.append(_shared_path)

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models import User
from auth.jwt_auth import get_current_user, get_optional_user
from exceptions import UnauthorizedException, ForbiddenException


async def get_current_user_db(
    token_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """JWT 토큰에서 DB 유저 객체를 반환"""
    user_id = int(token_data.get("sub", 0))
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise UnauthorizedException("User not found or inactive")
    return user


async def get_optional_user_db(
    token_data: dict = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> User | None:
    """선택적 인증 - 비로그인도 허용"""
    if token_data is None:
        return None
    user_id = int(token_data.get("sub", 0))
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    return user


async def get_admin_user(
    user: User = Depends(get_current_user_db),
) -> User:
    """관리자 전용 의존성"""
    if not user.is_admin:
        raise ForbiddenException("Admin access required")
    return user


def get_pagination(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
):
    """페이지네이션 파라미터"""
    return {"page": page, "size": size, "offset": (page - 1) * size}
