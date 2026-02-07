"""인증 API v1"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user_db
from schemas.auth import UserCreate, UserLogin, TokenResponse, RefreshTokenRequest, UserResponse
from schemas.common import MessageResponse
from services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
async def register(data: UserCreate, db: Session = Depends(get_db)):
    result = auth_service.register(
        db, data.email, data.password, data.name,
        phone=data.phone, company_code=data.company_code,
    )
    return TokenResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        user=UserResponse(
            id=result["user"].id,
            email=result["user"].email,
            name=result["user"].name,
            phone=result["user"].phone,
            company_name=result["company_name"],
            is_admin=result["user"].is_admin,
        ),
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: Session = Depends(get_db)):
    result = auth_service.login(db, data.email, data.password)
    return TokenResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        user=UserResponse(
            id=result["user"].id,
            email=result["user"].email,
            name=result["user"].name,
            phone=result["user"].phone,
            company_name=result["company_name"],
            is_admin=result["user"].is_admin,
        ),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshTokenRequest, db: Session = Depends(get_db)):
    result = auth_service.refresh_tokens(db, data.refresh_token)
    return TokenResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        user=UserResponse(
            id=result["user"].id,
            email=result["user"].email,
            name=result["user"].name,
            phone=result["user"].phone,
            company_name=result["company_name"],
            is_admin=result["user"].is_admin,
        ),
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(user=Depends(get_current_user_db), db: Session = Depends(get_db)):
    auth_service.logout(db, user)
    return MessageResponse(message="Logged out successfully")
