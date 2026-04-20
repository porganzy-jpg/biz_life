"""출퇴근 시간 API"""
import logging
import httpx

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from config import settings
from services.property_service import PropertyService
from exceptions import NotFoundException
from scoring.geo_utils import haversine

logger = logging.getLogger("homefinder.commute")

router = APIRouter()

# Average transit speed in Seoul (km/h) — used as fallback
AVG_TRANSIT_SPEED_KMH = 25
AVG_DRIVING_SPEED_KMH = 30


def _estimate_commute(lat: float, lng: float, wp_lat: float, wp_lng: float) -> dict:
    """Straight-line distance fallback estimate."""
    dist_m = haversine(lat, lng, wp_lat, wp_lng)
    dist_km = dist_m / 1000
    transit_min = round(dist_km / AVG_TRANSIT_SPEED_KMH * 60)
    driving_min = round(dist_km / AVG_DRIVING_SPEED_KMH * 60)
    return {
        "distance_km": round(dist_km, 1),
        "transit_minutes": transit_min,
        "driving_minutes": driving_min,
        "method": "estimate",
    }


def _kakao_commute(lat: float, lng: float, wp_lat: float, wp_lng: float) -> dict | None:
    """Use Kakao Mobility Directions API for actual commute time."""
    api_key = settings.KAKAO_REST_API_KEY
    if not api_key:
        return None

    url = "https://apis-navi.kakaomobility.com/v1/directions"
    headers = {"Authorization": f"KakaoAK {api_key}"}
    params = {
        "origin": f"{lng},{lat}",
        "destination": f"{wp_lng},{wp_lat}",
    }

    try:
        resp = httpx.get(url, headers=headers, params=params, timeout=5.0)
        if resp.status_code != 200:
            logger.warning(f"Kakao Directions API error: {resp.status_code}")
            return None

        data = resp.json()
        routes = data.get("routes", [])
        if not routes or routes[0].get("result_code") != 0:
            return None

        summary = routes[0].get("summary", {})
        duration_sec = summary.get("duration", 0)
        distance_m = summary.get("distance", 0)

        return {
            "distance_km": round(distance_m / 1000, 1),
            "driving_minutes": round(duration_sec / 60),
            "method": "kakao_navi",
        }
    except Exception as e:
        logger.warning(f"Kakao Directions API failed: {e}")
        return None


@router.get("/{property_id}")
def get_commute_time(property_id: int, db: Session = Depends(get_db)):
    """매물에서 직장까지 출퇴근 시간 계산"""
    wp_lat = settings.WORKPLACE_LAT
    wp_lng = settings.WORKPLACE_LNG

    if not wp_lat or not wp_lng:
        raise HTTPException(
            status_code=400,
            detail="직장 좌표가 설정되지 않았습니다. .env에 WORKPLACE_LAT, WORKPLACE_LNG를 설정하세요.",
        )

    svc = PropertyService(db)
    try:
        prop = svc.get_property(property_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e.detail))

    if not prop.lat or not prop.lng:
        raise HTTPException(status_code=400, detail="매물에 좌표 정보가 없습니다.")

    # Try Kakao Directions API first, fallback to distance estimate
    result = _kakao_commute(prop.lat, prop.lng, wp_lat, wp_lng)
    if result is None:
        result = _estimate_commute(prop.lat, prop.lng, wp_lat, wp_lng)

    return {
        "property_id": property_id,
        "workplace": {
            "address": settings.WORKPLACE_ADDRESS or "(설정되지 않음)",
            "lat": wp_lat,
            "lng": wp_lng,
        },
        **result,
    }
