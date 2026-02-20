"""
스크래퍼 API - 데이터 수집 관리 엔드포인트

POST /api/v1/scraper/scan     - Trigger manual scan for a district
GET  /api/v1/scraper/status   - Get scraper status
POST /api/v1/scraper/schedule - Configure auto-scan schedule
GET  /api/v1/scraper/preview  - Preview what scraper would find (dry run)
GET  /api/v1/scraper/history  - Get scan history
"""
import asyncio
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from backend.config import settings

logger = logging.getLogger("homefinder.api.scraper")

router = APIRouter()

# ──────────── Module-level scraper scheduler singleton ────────────

_scheduler = None
_scheduler_lock = asyncio.Lock() if hasattr(asyncio, 'Lock') else None


def _get_scheduler():
    """Get or create the ScrapingScheduler singleton."""
    global _scheduler
    if _scheduler is None:
        from backend.scraper.scheduler import ScrapingScheduler
        _scheduler = ScrapingScheduler(
            db_session_factory=SessionLocal,
            settings=settings,
        )
    return _scheduler


# ──────────── Request/Response Models ────────────

class ScanRequest(BaseModel):
    """Manual scan request."""
    district: str = Field(description="스캔할 구 이름 (e.g., 마포구)")
    property_type: str = Field(
        default="아파트",
        description="매물 유형 (아파트, 토지 등)",
    )


class ScheduleRequest(BaseModel):
    """Schedule configuration request."""
    districts: List[str] = Field(
        description="스캔 대상 구 목록",
    )
    property_types: List[str] = Field(
        default=["아파트"],
        description="스캔 대상 매물 유형 목록",
    )
    interval_hours: float = Field(
        default=24.0,
        ge=0.5,
        le=168.0,
        description="스캔 주기 (시간)",
    )


class ScheduleStopRequest(BaseModel):
    """Schedule stop request."""
    confirm: bool = Field(default=True, description="중지 확인")


# ──────────── API Endpoints ────────────

@router.post("/scan")
async def trigger_scan(
    body: ScanRequest,
    background_tasks: BackgroundTasks,
):
    """
    Trigger a manual scan for a specific district and property type.

    The scan runs in the background. Use GET /status to check progress.
    """
    scraper_enabled = getattr(settings, "SCRAPER_ENABLED", True)
    if not scraper_enabled:
        raise HTTPException(
            status_code=403,
            detail="스크래퍼가 비활성화되어 있습니다 (SCRAPER_ENABLED=False)",
        )

    scheduler = _get_scheduler()

    if scheduler._is_scanning:
        raise HTTPException(
            status_code=409,
            detail="이미 스캔이 진행 중입니다. 완료 후 다시 시도해주세요.",
        )

    # Validate district
    valid_districts = settings.TARGET_DISTRICTS + getattr(settings, "TARGET_SUBURBS", [])
    # Also accept any Korean district name (don't strictly restrict)

    async def _run_scan():
        try:
            result = await scheduler.run_scan(body.district, body.property_type)
            logger.info(
                "Manual scan completed: %s/%s -> new=%d, updated=%d",
                body.district, body.property_type, result.new, result.updated,
            )
        except Exception as e:
            logger.error("Manual scan error: %s", e)

    background_tasks.add_task(_run_scan)

    return {
        "message": f"{body.district} ({body.property_type}) 스캔을 시작합니다",
        "district": body.district,
        "property_type": body.property_type,
        "status": "started",
    }


@router.get("/status")
async def get_scraper_status():
    """
    Get current scraper status including:
    - Whether a scan is in progress
    - Last scan time
    - Cumulative counts (new, updated, errors)
    - Schedule configuration
    - Recent scan results
    """
    scheduler = _get_scheduler()
    status = scheduler.get_scan_status()

    # Add config info
    status["config"] = {
        "scraper_enabled": getattr(settings, "SCRAPER_ENABLED", True),
        "rate_limit_sec": getattr(settings, "SCRAPER_RATE_LIMIT_SEC", 2.0),
        "default_interval_hours": getattr(settings, "SCRAPER_INTERVAL_HOURS", 24),
        "target_districts": settings.TARGET_DISTRICTS,
    }

    return status


@router.post("/schedule")
async def configure_schedule(body: ScheduleRequest):
    """
    Configure the auto-scan schedule.

    Sets up recurring scans for the specified districts and property types.
    """
    scraper_enabled = getattr(settings, "SCRAPER_ENABLED", True)
    if not scraper_enabled:
        raise HTTPException(
            status_code=403,
            detail="스크래퍼가 비활성화되어 있습니다 (SCRAPER_ENABLED=False)",
        )

    scheduler = _get_scheduler()

    config = scheduler.schedule_scan(
        districts=body.districts,
        property_types=body.property_types,
        interval_hours=body.interval_hours,
    )

    return {
        "message": "스캔 스케줄이 설정되었습니다",
        "schedule": config,
    }


@router.post("/schedule/stop")
async def stop_schedule(body: ScheduleStopRequest = ScheduleStopRequest()):
    """Stop the auto-scan scheduler."""
    scheduler = _get_scheduler()
    scheduler.stop_schedule()

    return {
        "message": "스캔 스케줄이 중지되었습니다",
        "scheduler_running": False,
    }


@router.get("/preview")
async def preview_scan(
    district: str = Query(description="미리보기할 구 이름"),
    property_type: str = Query(
        default="아파트",
        description="매물 유형",
    ),
):
    """
    Preview what the scraper would find for a district (dry run).

    Does NOT save any data to the database. Shows what would be
    discovered including new vs. existing property counts.
    """
    scraper_enabled = getattr(settings, "SCRAPER_ENABLED", True)
    if not scraper_enabled:
        raise HTTPException(
            status_code=403,
            detail="스크래퍼가 비활성화되어 있습니다",
        )

    scheduler = _get_scheduler()

    try:
        preview = await scheduler.preview_scan(district, property_type)
    except Exception as e:
        logger.error("Preview scan error: %s", e)
        raise HTTPException(
            status_code=502,
            detail=f"미리보기 스캔 실패: {str(e)}",
        )

    return preview


@router.get("/history")
async def get_scan_history(
    limit: int = Query(20, ge=1, le=100, description="조회 건수"),
    offset: int = Query(0, ge=0, description="시작 위치"),
):
    """Get paginated scan history."""
    scheduler = _get_scheduler()
    history = scheduler.get_scan_history(limit=limit, offset=offset)

    return {
        "items": history,
        "count": len(history),
        "total": len(scheduler._scan_history),
    }
