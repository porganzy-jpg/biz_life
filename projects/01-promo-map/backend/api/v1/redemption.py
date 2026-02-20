"""할인 코드 발급/사용 API v1"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user_db
from models import User
from services import redemption_service

router = APIRouter(prefix="/redeem", tags=["redemption"])


# === Request/Response 스키마 ===

class GenerateCodeRequest(BaseModel):
    store_id: int
    discount_id: int


class ValidateCodeRequest(BaseModel):
    code: str


class CompleteRedemptionRequest(BaseModel):
    code: str
    amount: Optional[float] = 0


# === 엔드포인트 ===

@router.post("/generate")
async def generate_code(
    body: GenerateCodeRequest,
    user: User = Depends(get_current_user_db),
    db: Session = Depends(get_db),
):
    """할인 사용 코드 발급 (8자리, 5분 만료)"""
    result = redemption_service.generate_redemption_code(
        db=db,
        user_id=user.id,
        store_id=body.store_id,
        discount_id=body.discount_id,
    )
    return result


@router.post("/validate")
async def validate_code(
    body: ValidateCodeRequest,
    user: User = Depends(get_current_user_db),
):
    """코드 유효성 검증"""
    result = redemption_service.validate_redemption(body.code)
    return result


@router.post("/complete")
async def complete_code(
    body: CompleteRedemptionRequest,
    user: User = Depends(get_current_user_db),
    db: Session = Depends(get_db),
):
    """코드 사용 완료 처리"""
    result = redemption_service.complete_redemption(
        db=db,
        code=body.code,
        amount=body.amount or 0,
    )
    return result


@router.get("/history")
async def get_history(
    user: User = Depends(get_current_user_db),
):
    """사용 완료 코드 거래 내역"""
    items = redemption_service.get_user_redemptions(user.id)
    return {"items": items, "total": len(items)}


@router.get("/stats")
async def get_stats(
    user: User = Depends(get_current_user_db),
):
    """절약 통계"""
    stats = redemption_service.get_savings_stats(user.id)
    return stats
