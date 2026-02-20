"""맞춤 매칭 API - 지능형 추천 + 알림 관리"""
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from services.matching_engine import MatchingEngine
from services.alert_service import AlertService
from exceptions import NotFoundException

router = APIRouter()


# ── Pydantic Models ──

class ProfileWeightsUpdate(BaseModel):
    """매칭 가중치 수동 조정"""
    w_location: Optional[float] = Field(None, ge=0, le=1.0, description="위치 가중치")
    w_price: Optional[float] = Field(None, ge=0, le=1.0, description="가격 가중치")
    w_size: Optional[float] = Field(None, ge=0, le=1.0, description="규모 가중치")
    w_quality: Optional[float] = Field(None, ge=0, le=1.0, description="품질 가중치")
    w_opportunity: Optional[float] = Field(None, ge=0, le=1.0, description="기회 가중치")
    w_urgency: Optional[float] = Field(None, ge=0, le=1.0, description="긴급 가중치")


class ProfilePreferencesUpdate(BaseModel):
    """선호도 수동 조정"""
    district_weights: Optional[dict] = Field(None, description="지역별 가중치 {'마포구': 0.9, ...}")
    price_min_krw: Optional[int] = Field(None, description="최소 예산 (원)")
    price_max_krw: Optional[int] = Field(None, description="최대 예산 (원)")
    price_sweet_min_krw: Optional[int] = Field(None, description="스윗스팟 하한")
    price_sweet_max_krw: Optional[int] = Field(None, description="스윗스팟 상한")
    area_preferred_m2: Optional[float] = Field(None, description="선호 면적 (m2)")
    area_min_m2: Optional[float] = Field(None, description="최소 면적 (m2)")
    area_max_m2: Optional[float] = Field(None, description="최대 면적 (m2)")
    preferred_types: Optional[list] = Field(None, description="선호 매물 유형")
    preferred_floor_min: Optional[int] = Field(None, description="선호 최소 층수")
    preferred_floor_max: Optional[int] = Field(None, description="선호 최대 층수")
    preferred_direction: Optional[str] = Field(None, description="선호 향 (남향 등)")
    max_building_age: Optional[int] = Field(None, description="최대 허용 연식")
    max_subway_distance: Optional[float] = Field(None, description="최대 지하철 거리 (m)")


class AlertSettingsUpdate(BaseModel):
    """알림 설정 업데이트"""
    enabled: Optional[bool] = Field(None, description="알림 활성화")
    telegram_enabled: Optional[bool] = Field(None, description="텔레그램 알림")
    instant_threshold: Optional[float] = Field(None, ge=0, le=100, description="즉시 알림 임계치")
    daily_threshold: Optional[float] = Field(None, ge=0, le=100, description="일간 다이제스트 임계치")
    weekly_threshold: Optional[float] = Field(None, ge=0, le=100, description="주간 요약 임계치")
    quiet_start_hour: Optional[int] = Field(None, ge=0, le=23, description="조용한 시간 시작")
    quiet_end_hour: Optional[int] = Field(None, ge=0, le=23, description="조용한 시간 종료")
    dedup_hours: Optional[int] = Field(None, ge=1, le=168, description="중복 방지 시간")


class ActionLearnBody(BaseModel):
    """행동 학습 요청"""
    action_type: str = Field(description="행동 유형: candidate_add, rate_high, rate_low, reject, shortlist")
    property_data: dict = Field(description="매물 정보 (district, price_krw, area_m2 등)")


# ── Routes ──

@router.get("/top")
def get_top_matches(
    limit: int = Query(default=20, ge=1, le=100, description="반환 건수"),
    db: Session = Depends(get_db),
):
    """맞춤 추천 상위 매물 목록"""
    engine = MatchingEngine(db)
    matches = engine.find_top_matches(limit=limit)
    return {
        "count": len(matches),
        "matches": matches,
    }


@router.get("/explain/{property_id}")
def explain_match(
    property_id: int,
    db: Session = Depends(get_db),
):
    """매물 매칭 점수 상세 설명 (한국어)"""
    engine = MatchingEngine(db)
    result = engine.explain_match(property_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/profile")
def get_user_profile(
    db: Session = Depends(get_db),
):
    """현재 사용자 선호 프로필 조회"""
    engine = MatchingEngine(db)
    profile = engine.get_or_create_profile()
    return engine._profile_to_dict(profile)


@router.post("/profile/learn")
def learn_profile(
    db: Session = Depends(get_db),
):
    """저장된 검색 + 후보 매물 데이터에서 프로필 자동 학습"""
    engine = MatchingEngine(db)
    result = engine.build_user_profile()
    return {
        "message": "프로필 학습이 완료되었습니다",
        "profile": result,
    }


@router.post("/profile/action")
def learn_from_action(
    body: ActionLearnBody,
    db: Session = Depends(get_db),
):
    """사용자 행동에서 실시간 학습"""
    valid_actions = {"candidate_add", "rate_high", "rate_low", "reject", "shortlist"}
    if body.action_type not in valid_actions:
        raise HTTPException(
            status_code=400,
            detail=f"유효하지 않은 행동입니다: {body.action_type}. "
                   f"허용: {', '.join(valid_actions)}"
        )

    engine = MatchingEngine(db)
    result = engine.update_profile_from_action(body.action_type, body.property_data)
    return {
        "message": "프로필이 업데이트되었습니다",
        "profile": result,
    }


@router.put("/profile/weights")
def update_profile_weights(
    body: ProfileWeightsUpdate,
    db: Session = Depends(get_db),
):
    """매칭 가중치 수동 조정"""
    engine = MatchingEngine(db)
    profile = engine.get_or_create_profile()

    if body.w_location is not None:
        profile.w_location = body.w_location
    if body.w_price is not None:
        profile.w_price = body.w_price
    if body.w_size is not None:
        profile.w_size = body.w_size
    if body.w_quality is not None:
        profile.w_quality = body.w_quality
    if body.w_opportunity is not None:
        profile.w_opportunity = body.w_opportunity
    if body.w_urgency is not None:
        profile.w_urgency = body.w_urgency

    db.commit()
    db.refresh(profile)
    return {
        "message": "가중치가 업데이트되었습니다",
        "profile": engine._profile_to_dict(profile),
    }


@router.put("/profile/preferences")
def update_profile_preferences(
    body: ProfilePreferencesUpdate,
    db: Session = Depends(get_db),
):
    """선호도 수동 조정"""
    engine = MatchingEngine(db)
    profile = engine.get_or_create_profile()

    if body.district_weights is not None:
        profile.district_weights_json = json.dumps(body.district_weights, ensure_ascii=False)
    if body.price_min_krw is not None:
        profile.price_min_krw = body.price_min_krw
    if body.price_max_krw is not None:
        profile.price_max_krw = body.price_max_krw
    if body.price_sweet_min_krw is not None:
        profile.price_sweet_min_krw = body.price_sweet_min_krw
    if body.price_sweet_max_krw is not None:
        profile.price_sweet_max_krw = body.price_sweet_max_krw
    if body.area_preferred_m2 is not None:
        profile.area_preferred_m2 = body.area_preferred_m2
    if body.area_min_m2 is not None:
        profile.area_min_m2 = body.area_min_m2
    if body.area_max_m2 is not None:
        profile.area_max_m2 = body.area_max_m2
    if body.preferred_types is not None:
        profile.preferred_types_json = json.dumps(body.preferred_types, ensure_ascii=False)
    if body.preferred_floor_min is not None:
        profile.preferred_floor_min = body.preferred_floor_min
    if body.preferred_floor_max is not None:
        profile.preferred_floor_max = body.preferred_floor_max
    if body.preferred_direction is not None:
        profile.preferred_direction = body.preferred_direction
    if body.max_building_age is not None:
        profile.max_building_age = body.max_building_age
    if body.max_subway_distance is not None:
        profile.max_subway_distance = body.max_subway_distance

    db.commit()
    db.refresh(profile)
    return {
        "message": "선호도가 업데이트되었습니다",
        "profile": engine._profile_to_dict(profile),
    }


@router.get("/alerts")
def get_alert_history(
    limit: int = Query(default=50, ge=1, le=200, description="반환 건수"),
    offset: int = Query(default=0, ge=0, description="오프셋"),
    db: Session = Depends(get_db),
):
    """매칭 알림 이력 조회"""
    engine = MatchingEngine(db)
    alerts = engine.get_alert_history(limit=limit, offset=offset)
    return {
        "count": len(alerts),
        "alerts": alerts,
    }


@router.post("/alerts/{alert_id}/read")
def mark_alert_read(
    alert_id: int,
    db: Session = Depends(get_db),
):
    """알림 읽음 처리"""
    svc = AlertService(db)
    if svc.mark_alert_read(alert_id):
        return {"message": "읽음 처리되었습니다"}
    raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다")


@router.get("/settings")
def get_alert_settings(
    db: Session = Depends(get_db),
):
    """알림 설정 조회"""
    engine = MatchingEngine(db)
    return engine.get_alert_settings()


@router.put("/settings")
def update_alert_settings(
    body: AlertSettingsUpdate,
    db: Session = Depends(get_db),
):
    """알림 설정 업데이트"""
    engine = MatchingEngine(db)
    data = body.dict(exclude_none=True)
    result = engine.update_alert_settings(data)
    return {
        "message": "알림 설정이 업데이트되었습니다",
        "settings": result,
    }


@router.post("/check-new")
def check_new_listings(
    hours: int = Query(default=24, ge=1, le=168, description="검색 시간 범위"),
    db: Session = Depends(get_db),
):
    """신규 매물 매칭 체크 및 알림 생성"""
    engine = MatchingEngine(db)
    alerts = engine.check_new_listings(hours=hours)
    return {
        "message": f"신규 매물 체크 완료",
        "alerts_created": len(alerts),
        "alerts": alerts,
    }


@router.post("/send-digest")
def send_daily_digest(
    db: Session = Depends(get_db),
):
    """일간 매칭 다이제스트 전송"""
    svc = AlertService(db)
    message = svc.build_daily_digest()
    if not message:
        return {"message": "전송할 매칭 결과가 없습니다", "sent": False}

    sent = svc.send_daily_digest()
    return {
        "message": "일간 다이제스트가 전송되었습니다" if sent else "전송 실패",
        "sent": sent,
        "preview": message[:500],
    }
