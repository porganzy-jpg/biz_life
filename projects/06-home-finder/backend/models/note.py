"""메모/태그"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text
from database import Base


class PropertyNote(Base):
    __tablename__ = "property_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    property_id = Column(Integer)
    candidate_id = Column(Integer)
    note_type = Column(String(30), default="general")  # general, visit, price, risk
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
