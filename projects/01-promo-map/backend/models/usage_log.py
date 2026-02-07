"""UsageLog 모델"""
from datetime import datetime
from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    discount_id = Column(Integer, ForeignKey("discounts.id"), nullable=False)
    saved_amount = Column(Float, default=0)
    used_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="usage_logs")
    store = relationship("Store")
    discount = relationship("Discount")
