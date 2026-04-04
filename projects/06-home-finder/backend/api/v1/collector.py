"""
데이터 수집 관리 API
수동 수집 트리거, 스케줄러 상태 확인, 수집 이력 조회
"""
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request

logger = logging.getLogger("homefinder.api.collector")

router = APIRouter()

VALID_COLLECTORS = ["molit", "land", "naver", "auction", "subscription", "kb_index"]


def _get_scheduler(request: Request):
    """app.state에서 스케줄러 인스턴스 가져오기"""
    scheduler = getattr(request.app.state, "scheduler", None)
    if not scheduler:
        raise HTTPException(status_code=503, detail="스케줄러가 아직 시작되지 않았습니다")
    return scheduler


# ──────────── 수동 수집 트리거 ────────────

@router.post("/run/{collector_name}")
async def run_collector(
    request: Request,
    collector_name: str,
    background_tasks: BackgroundTasks,
    months_back: int = Query(1, ge=1, le=12, description="수집 개월 수 (실거래가용)"),
):
    """
    특정 수집기를 즉시 실행합니다.

    collector_name: molit, naver, auction, subscription, kb_index
    """
    if collector_name not in VALID_COLLECTORS:
        raise HTTPException(
            status_code=400,
            detail=f"유효하지 않은 수집기: {collector_name}. 가능: {VALID_COLLECTORS}",
        )

    scheduler = _get_scheduler(request)

    # molit/land는 months_back 파라미터를 지원
    if collector_name in ("molit", "land"):
        def _run_with_months(name=collector_name, mb=months_back):
            from backend.config import settings
            if name == "molit":
                from collectors.molit_collector import MolitCollector
                collector = MolitCollector(api_key=settings.PUBLIC_DATA_API_KEY, target_districts=settings.TARGET_DISTRICTS)
            else:
                from collectors.land_collector import LandCollector
                collector = LandCollector(api_key=settings.PUBLIC_DATA_API_KEY, target_districts=settings.TARGET_DISTRICTS)
            collector.run(months_back=mb)
        background_tasks.add_task(_run_with_months)
    else:
        job_map = {
            "naver": scheduler.job_collect_naver,
            "auction": scheduler.job_collect_auctions,
            "subscription": scheduler.job_collect_subscriptions,
            "kb_index": scheduler.job_collect_kb_index,
        }
        background_tasks.add_task(job_map[collector_name])

    return {
        "collector": collector_name,
        "status": "started",
        "message": f"{collector_name} 수집을 백그라운드에서 시작합니다",
        "months_back": months_back if collector_name == "molit" else None,
    }


@router.post("/run-all")
async def run_all_collectors(request: Request, background_tasks: BackgroundTasks):
    """모든 수집기를 순차 실행합니다. 개별 실패 시 나머지 계속 진행."""
    scheduler = _get_scheduler(request)

    def _run_all():
        results = {}
        for name, job_func in [
            ("molit", scheduler.job_collect_molit),
            ("naver", scheduler.job_collect_naver),
            ("auction", scheduler.job_collect_auctions),
            ("subscription", scheduler.job_collect_subscriptions),
        ]:
            try:
                job_func()
                results[name] = "success"
            except Exception as e:
                results[name] = f"failed: {e}"
                logger.error(f"run-all: {name} failed: {e}")
        logger.info(f"run-all complete: {results}")

    background_tasks.add_task(_run_all)

    return {
        "status": "started",
        "message": "전체 수집을 백그라운드에서 시작합니다 (국토부→네이버→경매→청약)",
    }


# ──────────── 스케줄러 상태 ────────────

@router.get("/scheduler/status")
async def scheduler_status(request: Request):
    """스케줄러 상태 및 등록된 작업 목록 조회"""
    sched = getattr(request.app.state, "scheduler", None)
    if not sched:
        return {"running": False, "jobs": [], "error": "스케줄러 미시작"}

    jobs = sched.get_jobs()
    return {
        "running": True,
        "job_count": len(jobs),
        "jobs": jobs,
    }


@router.post("/scheduler/trigger/{job_id}")
async def trigger_job(request: Request, job_id: str):
    """특정 스케줄 작업을 즉시 실행"""
    scheduler = _get_scheduler(request)

    success = scheduler.run_job_now(job_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"작업을 찾을 수 없음: {job_id}")

    return {"job_id": job_id, "status": "triggered"}


# ──────────── 수집 이력 ────────────

@router.get("/history")
async def collection_history(
    limit: int = Query(20, ge=1, le=100),
):
    """최근 수집 이력 조회"""
    from database import SessionLocal
    from models.data_collection_log import DataCollectionLog

    db = SessionLocal()
    try:
        logs = (
            db.query(DataCollectionLog)
            .order_by(DataCollectionLog.started_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": log.id,
                "collector": log.collector_name,
                "status": log.status,
                "fetched": log.records_fetched,
                "new": log.records_new,
                "updated": log.records_updated,
                "error": log.error_message,
                "started_at": str(log.started_at) if log.started_at else None,
                "finished_at": str(log.finished_at) if log.finished_at else None,
            }
            for log in logs
        ]
    finally:
        db.close()
