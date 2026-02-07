"""Favorite 모델"""
from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base


class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "store_id", name="uq_user_store_favorite"),
    )

    user = relationship("User", back_populates="favorites")
    store = relationship("Store", back_populates="favorites")
