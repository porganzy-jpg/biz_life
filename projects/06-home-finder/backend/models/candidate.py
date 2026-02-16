"""후보 매물 (파이프라인)"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Index
from database import Base


class CandidateProperty(Base):
    __tablename__ = "candidate_properties"

    id = Column(Integer, primary_key=True, autoincrement=True)
    property_id = Column(Integer)  # properties.id FK
    auction_id = Column(Integer)  # auction_listings.id FK (optional)
    subscription_id = Column(Integer)  # subscription_opportunities.id FK (optional)

    # Pipeline status: 발견 → 조사 → 관심 → 방문예정 → 방문완료 → 결정
    status = Column(String(20), default="발견")
    priority = Column(Integer, default=3)  # 1=highest, 5=lowest
    rating = Column(Integer)  # 1-5 (방문 후 평점)

    visit_date = Column(DateTime)
    visit_notes = Column(Text)
    decision = Column(String(20))  # 보류, 탈락, 최종후보
    decision_reason = Column(Text)

    tags = Column(String(200))  # comma-separated
    pros = Column(Text)
    cons = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_cand_status", "status"),
        Index("ix_cand_priority", "priority"),
    )
