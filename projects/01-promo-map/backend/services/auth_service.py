"""인증 서비스"""
import sys
import os

_shared_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "shared")
if _shared_path not in sys.path:
    sys.path.append(_shared_path)

from datetime import datetime, timedelta, timezone
import jwt as pyjwt
from sqlalchemy.orm import Session

from config import settings
from models import User, Company
from repositories.user_repo import UserRepository
from repositories.company_repo import CompanyRepository
from auth.password import hash_password, verify_password
from exceptions import (
    BadRequestException, UnauthorizedException, NotFoundException, DuplicateException,
)


def _create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    to_encode["exp"] = expire
    to_encode["type"] = "access"
    return pyjwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def _create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)
    to_encode["exp"] = expire
    to_encode["type"] = "refresh"
    return pyjwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def register(db: Session, email: str, password: str, name: str,
             phone: str = "", company_code: str = None) -> dict:
    user_repo = UserRepository(db)
    company_repo = CompanyRepository(db)

    if user_repo.get_by_email(email):
        raise DuplicateException("Email already registered")

    company = None
    if company_code:
        company = company_repo.get_by_code(company_code)

    user = user_repo.create(
        email=email,
        hashed_password=hash_password(password),
        name=name,
        phone=phone,
        company_id=company.id if company else None,
    )

    access_token = _create_access_token({"sub": str(user.id), "email": user.email})
    refresh_token = _create_refresh_token({"sub": str(user.id)})
    user_repo.update_refresh_token(user, refresh_token)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user,
        "company_name": company.name if company else None,
    }


def login(db: Session, email: str, password: str) -> dict:
    user_repo = UserRepository(db)

    user = user_repo.get_by_email(email)
    if not user or not verify_password(password, user.hashed_password):
        raise UnauthorizedException("Invalid email or password")

    if not user.is_active:
        raise UnauthorizedException("Account is deactivated")

    access_token = _create_access_token({"sub": str(user.id), "email": user.email})
    refresh_token = _create_refresh_token({"sub": str(user.id)})
    user_repo.update_refresh_token(user, refresh_token)
    user_repo.update_last_login(user)

    company_name = None
    if user.company_id and user.company:
        company_name = user.company.name

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user,
        "company_name": company_name,
    }


def refresh_tokens(db: Session, refresh_token: str) -> dict:
    try:
        payload = pyjwt.decode(refresh_token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except pyjwt.ExpiredSignatureError:
        raise UnauthorizedException("Refresh token expired")
    except pyjwt.InvalidTokenError:
        raise UnauthorizedException("Invalid refresh token")

    if payload.get("type") != "refresh":
        raise UnauthorizedException("Invalid token type")

    user_repo = UserRepository(db)
    user = user_repo.get_by_id(int(payload["sub"]))

    if not user or user.refresh_token != refresh_token:
        raise UnauthorizedException("Invalid refresh token")

    new_access = _create_access_token({"sub": str(user.id), "email": user.email})
    new_refresh = _create_refresh_token({"sub": str(user.id)})
    user_repo.update_refresh_token(user, new_refresh)

    company_name = user.company.name if user.company else None

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "user": user,
        "company_name": company_name,
    }


def logout(db: Session, user: User):
    user_repo = UserRepository(db)
    user_repo.update_refresh_token(user, None)
