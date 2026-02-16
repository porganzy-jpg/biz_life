"""
HomeFinder - 마지막 집 찾기
FastAPI 메인 앱 진입점
"""
import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager

# Path setup: project root + backend/ both need to be importable
PROJECT_ROOT = Path(__file__).parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BACKEND_DIR))

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from database import init_db, get_db, SessionLocal
from api.v1 import v1_router
from exceptions import register_exception_handlers
from middleware import RequestLoggingMiddleware
import seed_data

# Logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("homefinder")


# Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("HomeFinder starting up...")
    init_db()
    logger.info("Database initialized")
    seed_data.seed()
    logger.info("Seed data loaded")
    logger.info(f"Server ready on port {settings.PORT}")
    yield
    # Shutdown
    logger.info("HomeFinder shutting down...")


# FastAPI app
app = FastAPI(
    title="HomeFinder",
    description="마지막 집 찾기 - 부동산 매물 검색 & 분석 플랫폼",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging
app.add_middleware(RequestLoggingMiddleware)

# Exception handlers
register_exception_handlers(app)

# Static files
app.mount("/static", StaticFiles(directory=str(settings.STATIC_DIR)), name="static")

# Templates
templates = Jinja2Templates(directory=str(settings.TEMPLATES_DIR))

# API routers
app.include_router(v1_router)


# ──────────────── Template Routes (페이지 렌더링) ────────────────

@app.get("/", include_in_schema=False)
async def page_dashboard(request: Request):
    budget_min = f"{settings.BUDGET_MIN_KRW / 100_000_000:.0f}억"
    budget_max = f"{settings.BUDGET_MAX_KRW / 100_000_000:.0f}억"
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "budget_min": budget_min,
        "budget_max": budget_max,
        "target_districts": ", ".join(settings.TARGET_DISTRICTS),
    })


@app.get("/search", include_in_schema=False)
async def page_my_search(request: Request):
    return templates.TemplateResponse("my_search.html", {
        "request": request,
        "target_districts": settings.TARGET_DISTRICTS,
        "kakao_api_key": settings.KAKAO_REST_API_KEY,
    })


@app.get("/map", include_in_schema=False)
async def page_map(request: Request):
    return templates.TemplateResponse("map.html", {
        "request": request,
        "kakao_api_key": settings.KAKAO_REST_API_KEY,
    })


@app.get("/candidates", include_in_schema=False)
async def page_candidates(request: Request):
    return templates.TemplateResponse("candidates.html", {
        "request": request,
    })


@app.get("/areas", include_in_schema=False)
async def page_areas(request: Request):
    return templates.TemplateResponse("area_analysis.html", {
        "request": request,
    })


@app.get("/property/{property_id}", include_in_schema=False)
async def page_property_detail(request: Request, property_id: int):
    return templates.TemplateResponse("property_detail.html", {
        "request": request,
        "property_id": property_id,
    })


# ──────────────── Run ────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=True,
        reload_dirs=[str(PROJECT_ROOT)],
    )
