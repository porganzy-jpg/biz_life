"""저장된 검색조건"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text
from database import Base


class SavedSearch(Base):
    __tablename__ = "saved_searches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    criteria_json = Column(Text, nullable=False)  # JSON string
    alert_on_new = Column(Integer, default=1)
    alert_on_price_change = Column(Integer, default=0)
    last_matched_at = Column(DateTime)
    match_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
