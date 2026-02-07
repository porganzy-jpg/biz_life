"""
PromoMap - FastAPI 메인 앱
위치 기반 임직원 할인 서비스 (프로덕션)
"""
import sys
import os
import logging

# shared 모듈은 마지막에 추가 (로컬 모듈 우선)
_shared_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "shared")
if _shared_path not in sys.path:
    sys.path.append(_shared_path)

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.templating import Jinja2Templates
import uvicorn

from config import settings
from database import init_db
from seed_data import seed
from middleware import RequestLoggingMiddleware
from exceptions import register_exception_handlers
from api.v1 import v1_router
from admin.auth import router as admin_auth_router
from admin.routes import router as admin_routes_router

# 로깅 설정
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("promomap")

# FastAPI 앱
app = FastAPI(
    title="PromoMap API",
    version="2.0.0",
    description="위치 기반 임직원 할인 서비스",
)

# === 미들웨어 (역순 적용) ===
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SessionMiddleware, secret_key=settings.ADMIN_SESSION_SECRET)
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === 예외 핸들러 ===
register_exception_handlers(app)

# === 라우터 등록 ===
app.include_router(v1_router)
app.include_router(admin_auth_router)
app.include_router(admin_routes_router)

# === Rate Limiting ===
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded

    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
except ImportError:
    logger.warning("slowapi not installed - rate limiting disabled")

# === 정적 파일 + 템플릿 ===
_project_root = os.path.dirname(os.path.dirname(__file__))
_static_dir = os.path.join(_project_root, "static")
_templates_dir = os.path.join(_project_root, "templates")

if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")

templates = Jinja2Templates(directory=_templates_dir)


# === 이벤트 ===
@app.on_event("startup")
async def startup():
    init_db()
    seed()
    logger.info("PromoMap started successfully")


# === 페이지 라우트 ===
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "kakao_api_key": settings.KAKAO_MAP_API_KEY,
    })


@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    return templates.TemplateResponse("admin/login.html", {"request": request})


@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard_page(request: Request):
    admin_id = request.session.get("admin_id")
    if not admin_id:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin/login")
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "admin_name": request.session.get("admin_name", "Admin"),
        "kakao_api_key": settings.KAKAO_MAP_API_KEY,
    })


@app.get("/admin/stores", response_class=HTMLResponse)
async def admin_stores_page(request: Request):
    admin_id = request.session.get("admin_id")
    if not admin_id:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin/login")
    return templates.TemplateResponse("admin/stores.html", {
        "request": request,
        "admin_name": request.session.get("admin_name", "Admin"),
        "kakao_api_key": settings.KAKAO_MAP_API_KEY,
    })


@app.get("/admin/discounts", response_class=HTMLResponse)
async def admin_discounts_page(request: Request):
    admin_id = request.session.get("admin_id")
    if not admin_id:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin/login")
    return templates.TemplateResponse("admin/discounts.html", {
        "request": request,
        "admin_name": request.session.get("admin_name", "Admin"),
    })


@app.get("/admin/companies", response_class=HTMLResponse)
async def admin_companies_page(request: Request):
    admin_id = request.session.get("admin_id")
    if not admin_id:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin/login")
    return templates.TemplateResponse("admin/companies.html", {
        "request": request,
        "admin_name": request.session.get("admin_name", "Admin"),
    })


@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(request: Request):
    admin_id = request.session.get("admin_id")
    if not admin_id:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin/login")
    return templates.TemplateResponse("admin/users.html", {
        "request": request,
        "admin_name": request.session.get("admin_name", "Admin"),
    })


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "PromoMap", "version": "2.0.0"}


if __name__ == "__main__":
    print("=" * 50)
    print("  PromoMap Server - http://localhost:8000")
    print("  Admin Panel - http://localhost:8000/admin/login")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000)
