"""어드민 세션 인증"""
import sys
import os

_shared_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "shared")
if _shared_path not in sys.path:
    sys.path.append(_shared_path)

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from database import get_db
from models import User
from auth.password import verify_password
from exceptions import UnauthorizedException

router = APIRouter(prefix="/admin", tags=["admin-auth"])


@router.post("/api/login")
async def admin_login(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    email = data.get("email", "")
    password = data.get("password", "")

    user = db.query(User).filter(User.email == email, User.is_admin == True).first()
    if not user or not verify_password(password, user.hashed_password):
        return JSONResponse(status_code=401, content={"detail": "Invalid credentials"})

    request.session["admin_id"] = user.id
    request.session["admin_email"] = user.email
    request.session["admin_name"] = user.name
    return {"status": "ok", "user": {"id": user.id, "name": user.name, "email": user.email}}


@router.post("/api/logout")
async def admin_logout(request: Request):
    request.session.clear()
    return {"status": "ok"}


def get_admin_session(request: Request, db: Session = Depends(get_db)) -> User:
    admin_id = request.session.get("admin_id")
    if not admin_id:
        raise UnauthorizedException("Admin login required")
    user = db.query(User).filter(User.id == admin_id, User.is_admin == True).first()
    if not user:
        request.session.clear()
        raise UnauthorizedException("Admin session invalid")
    return user
