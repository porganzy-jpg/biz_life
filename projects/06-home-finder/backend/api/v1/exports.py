"""내보내기 API - CSV 다운로드 및 HTML 보고서"""
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from database import get_db
from services.export_service import ExportService

router = APIRouter()


@router.get("/candidates/csv")
def export_candidates_csv(
    status: Optional[str] = Query(None, description="파이프라인 상태 필터 (단일)"),
    statuses: Optional[List[str]] = Query(None, description="파이프라인 상태 필터 (복수)"),
    min_score: Optional[float] = Query(None, ge=0, description="최소 종합 점수"),
    district: Optional[str] = Query(None, description="구 필터"),
    price_min: Optional[int] = Query(None, ge=0, description="최소 가격 (원)"),
    price_max: Optional[int] = Query(None, ge=0, description="최대 가격 (원)"),
    db: Session = Depends(get_db),
):
    """후보 매물 CSV 다운로드"""
    svc = ExportService(db)
    csv_content = svc.export_candidates_csv(
        status=status,
        statuses=statuses,
        min_score=min_score,
        district=district,
        price_min=price_min,
        price_max=price_max,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"homefinder_candidates_{timestamp}.csv"

    return Response(
        content=csv_content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/candidates/report")
def export_candidates_report(
    status: Optional[str] = Query(None, description="파이프라인 상태 필터 (단일)"),
    statuses: Optional[List[str]] = Query(None, description="파이프라인 상태 필터 (복수)"),
    min_score: Optional[float] = Query(None, ge=0, description="최소 종합 점수"),
    district: Optional[str] = Query(None, description="구 필터"),
    price_min: Optional[int] = Query(None, ge=0, description="최소 가격 (원)"),
    price_max: Optional[int] = Query(None, ge=0, description="최대 가격 (원)"),
    db: Session = Depends(get_db),
):
    """후보 매물 인쇄용 HTML 보고서 다운로드"""
    svc = ExportService(db)
    html_content = svc.export_candidates_report(
        status=status,
        statuses=statuses,
        min_score=min_score,
        district=district,
        price_min=price_min,
        price_max=price_max,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"homefinder_report_{timestamp}.html"

    return Response(
        content=html_content.encode("utf-8"),
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
        },
    )


@router.get("/properties/csv")
def export_properties_csv(
    district: Optional[str] = Query(None, description="구 필터"),
    price_min: Optional[int] = Query(None, ge=0, description="최소 가격 (원)"),
    price_max: Optional[int] = Query(None, ge=0, description="최대 가격 (원)"),
    score_min: Optional[float] = Query(None, ge=0, description="최소 종합 점수"),
    property_type: Optional[str] = Query(None, description="매물 유형"),
    db: Session = Depends(get_db),
):
    """매물 검색 결과 CSV 다운로드"""
    svc = ExportService(db)
    csv_content = svc.export_properties_csv(
        district=district,
        price_min=price_min,
        price_max=price_max,
        score_min=score_min,
        property_type=property_type,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"homefinder_properties_{timestamp}.csv"

    return Response(
        content=csv_content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
