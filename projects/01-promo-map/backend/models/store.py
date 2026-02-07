"""Store 모델"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Index
from sqlalchemy.orm import relationship
from database import Base


class Store(Base):
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    brand = Column(String(100), nullable=False)
    category = Column(String(50), default="general")
    address = Column(String(500), default="")
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    phone = Column(String(20), default="")
    icon_color = Column(String(7), default="#FF6B35")
    icon_letter = Column(String(2), default="S")
    is_active = Column(Boolean, default=True)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_store_location", "latitude", "longitude"),
    )

    discounts = relationship("Discount", back_populates="store")
    favorites = relationship("Favorite", back_populates="store", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="store", cascade="all, delete-orphan")
