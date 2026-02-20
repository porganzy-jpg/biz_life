"""맞춤 매칭 모델 - 사용자 선호 프로필 & 알림 이력"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Index
from database import Base


class UserProfile(Base):
    """사용자 선호도 프로필 (매칭 엔진 학습 결과)"""
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 지역 선호 가중치 (JSON: {"마포구": 0.9, "용산구": 0.85, ...})
    district_weights_json = Column(Text, default="{}")

    # 가격 선호
    price_min_krw = Column(Integer)
    price_max_krw = Column(Integer)
    price_sweet_min_krw = Column(Integer)  # 학습된 스윗스팟 하한
    price_sweet_max_krw = Column(Integer)  # 학습된 스윗스팟 상한

    # 면적 선호
    area_min_m2 = Column(Float)
    area_max_m2 = Column(Float)
    area_preferred_m2 = Column(Float)  # 선호 면적 중심값

    # 매물 특성 가중치 (0~1, 합계 자유)
    w_location = Column(Float, default=0.30)
    w_price = Column(Float, default=0.25)
    w_size = Column(Float, default=0.15)
    w_quality = Column(Float, default=0.15)
    w_opportunity = Column(Float, default=0.10)
    w_urgency = Column(Float, default=0.05)

    # 선호 특성
    preferred_types_json = Column(Text, default='["아파트"]')  # 매물 유형
    preferred_floor_min = Column(Integer)
    preferred_floor_max = Column(Integer)
    preferred_direction = Column(String(20))  # 선호 향
    max_building_age = Column(Integer)  # 최대 허용 연식
    max_subway_distance = Column(Float)  # 최대 지하철 거리 (m)

    # 학습 메타
    actions_count = Column(Integer, default=0)
    last_learned_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MatchAlert(Base):
    """매칭 알림 이력"""
    __tablename__ = "match_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    property_id = Column(Integer, nullable=False)
    match_score = Column(Float, nullable=False)

    # 점수 내역 JSON: {"location": 85, "price": 72, ...}
    score_breakdown_json = Column(Text)
    explanation = Column(Text)  # 한국어 설명

    alert_type = Column(String(30))  # instant, daily_digest, weekly
    sent_via = Column(String(20))  # telegram, web
    is_sent = Column(Integer, default=0)
    is_read = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime)

    __table_args__ = (
        Index("ix_alert_score", "match_score"),
        Index("ix_alert_created", "created_at"),
        Index("ix_alert_property", "property_id"),
    )


class AlertSettings(Base):
    """알림 설정"""
    __tablename__ = "alert_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 알림 활성화
    enabled = Column(Integer, default=1)
    telegram_enabled = Column(Integer, default=1)

    # 임계치
    instant_threshold = Column(Float, default=90.0)  # 즉시 알림 최소 점수
    daily_threshold = Column(Float, default=80.0)    # 일간 요약 최소 점수
    weekly_threshold = Column(Float, default=70.0)   # 주간 요약 최소 점수

    # 조용한 시간대
    quiet_start_hour = Column(Integer, default=22)  # 22:00
    quiet_end_hour = Column(Integer, default=8)      # 08:00

    # 중복 방지 (시간 단위)
    dedup_hours = Column(Integer, default=24)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
