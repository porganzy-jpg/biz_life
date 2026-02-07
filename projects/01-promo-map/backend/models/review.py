"""Review 모델"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, CheckConstraint
from sqlalchemy.orm import relationship
from database import Base


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    rating = Column(Integer, nullable=False)
    content = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_review_rating"),
    )

    user = relationship("User", back_populates="reviews")
    store = relationship("Store", back_populates="reviews")
