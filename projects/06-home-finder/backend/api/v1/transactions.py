"""실거래가 API"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from repositories.transaction_repo import TransactionRepository

router = APIRouter()


def _tx_to_dict(t):
    return {
        "id": t.id,
        "city": t.city,
        "district": t.district,
        "dong": t.dong,
        "name": t.name,
        "address": t.address,
        "transaction_date": t.transaction_date.isoformat() if t.transaction_date else None,
        "price_krw": t.price_krw,
        "area_exclusive": t.area_exclusive,
        "floor": t.floor,
        "built_year": t.built_year,
        "property_type": t.property_type,
        "price_per_m2": t.price_per_m2,
        "trade_type": getattr(t, "trade_type", "매매"),
        "deposit_krw": getattr(t, "deposit_krw", None),
        "monthly_rent_krw": getattr(t, "monthly_rent_krw", None),
        "source": t.source,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


@router.get("/")
def get_latest_transactions(
    limit: int = Query(50, ge=1, le=200, description="조회 건수"),
    db: Session = Depends(get_db),
):
    """최신 실거래가 조회"""
    repo = TransactionRepository(db)
    items = repo.get_latest_transactions(limit=limit)
    return {"items": [_tx_to_dict(t) for t in items], "count": len(items)}


@router.get("/trend")
def get_price_trend(
    district: str = Query(..., description="구"),
    dong: Optional[str] = Query(None, description="동"),
    name: Optional[str] = Query(None, description="단지명/건물명"),
    months: int = Query(24, ge=1, le=120, description="조회 개월 수"),
    db: Session = Depends(get_db),
):
    """가격 추이 조회 (구, 동, 단지명 기준)"""
    repo = TransactionRepository(db)
    transactions = repo.get_price_trend(
        district=district,
        dong=dong,
        name=name,
        months=months,
    )

    # Group by month for trend data points
    monthly_data = {}
    for t in transactions:
        if not t.transaction_date:
            continue
        month_key = t.transaction_date.strftime("%Y-%m")
        if month_key not in monthly_data:
            monthly_data[month_key] = {
                "prices": [],
                "prices_per_m2": [],
            }
        monthly_data[month_key]["prices"].append(t.price_krw or 0)
        if t.price_per_m2:
            monthly_data[month_key]["prices_per_m2"].append(t.price_per_m2)

    data_points = []
    for month_key in sorted(monthly_data.keys()):
        md = monthly_data[month_key]
        prices = md["prices"]
        prices_per_m2 = md["prices_per_m2"]
        avg_price = int(sum(prices) / len(prices)) if prices else 0
        avg_ppm2 = int(sum(prices_per_m2) / len(prices_per_m2)) if prices_per_m2 else None
        data_points.append({
            "month": month_key,
            "avg_price_krw": avg_price,
            "avg_price_per_m2": avg_ppm2,
            "transaction_count": len(prices),
            "min_price_krw": min(prices) if prices else None,
            "max_price_krw": max(prices) if prices else None,
        })

    # Overall change percentage
    overall_change_pct = None
    if len(data_points) >= 2:
        first_avg = data_points[0]["avg_price_krw"]
        last_avg = data_points[-1]["avg_price_krw"]
        if first_avg > 0:
            overall_change_pct = round((last_avg - first_avg) / first_avg * 100, 2)

    return {
        "district": district,
        "dong": dong,
        "name": name,
        "months": months,
        "data_points": data_points,
        "total_transactions": len(transactions),
        "overall_change_pct": overall_change_pct,
    }


@router.get("/district/{district}")
def get_transactions_by_district(
    district: str,
    months_back: int = Query(6, ge=1, le=60, description="조회 개월 수"),
    db: Session = Depends(get_db),
):
    """특정 구의 실거래 내역"""
    repo = TransactionRepository(db)
    items = repo.get_by_district(district, months_back=months_back)
    return {
        "district": district,
        "months_back": months_back,
        "items": [_tx_to_dict(t) for t in items],
        "count": len(items),
    }
