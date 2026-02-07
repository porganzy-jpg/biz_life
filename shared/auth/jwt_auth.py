"""
BIZ LIFE - JWT 인증 모듈
PromoMap, VoiceMemory 등에서 공통 사용
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "biz-life-dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

security = HTTPBearer(auto_error=False)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    JWT 액세스 토큰 생성

    Args:
        data: 토큰에 담을 페이로드 (예: {"sub": user_id})
        expires_delta: 만료 기간

    Returns:
        str: JWT 토큰 문자열
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    """
    JWT 토큰 검증

    Returns:
        dict: 디코딩된 페이로드

    Raises:
        HTTPException: 토큰이 유효하지 않을 때
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    FastAPI 의존성: 현재 인증된 사용자 반환

    Usage:
        @app.get("/protected")
        async def protected(user=Depends(get_current_user)):
            return {"user_id": user["sub"]}
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return verify_token(credentials.credentials)


def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Optional[dict]:
    """인증 선택적 의존성 (비로그인도 허용)"""
    if credentials is None:
        return None
    try:
        return verify_token(credentials.credentials)
    except HTTPException:
        return None
