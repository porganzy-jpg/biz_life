"""Notification 모델"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    ForeignKey, Text, Index,
)
from sqlalchemy.orm import relationship
from database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    discount_id = Column(Integer, ForeignKey("discounts.id"), nullable=False)
    title = Column(String(300), nullable=False)
    body = Column(Text, default="")
    distance_m = Column(Float, default=0)
    priority = Column(Integer, default=0)  # higher = more important
    seen_at = Column(DateTime, nullable=True)
    dismissed_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    converted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_notif_user_unseen", "user_id", "seen_at"),
        Index("idx_notif_user_created", "user_id", "created_at"),
        Index("idx_notif_dedup", "user_id", "store_id", "discount_id", "created_at"),
    )

    user = relationship("User")
    store = relationship("Store")
    discount = relationship("Discount")


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    max_radius_m = Column(Integer, default=500)
    quiet_hours_start = Column(String(5), default="22:00")  # HH:MM
    quiet_hours_end = Column(String(5), default="08:00")    # HH:MM
    enabled_categories = Column(Text, default="")  # comma-separated: food,cafe,shopping
    daily_limit = Column(Integer, default=50)
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")


class NotificationEngagement(Base):
    """사용자 카테고리 참여도 추적"""
    __tablename__ = "notification_engagements"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category = Column(String(50), nullable=False)
    click_count = Column(Integer, default=0)
    dismiss_count = Column(Integer, default=0)
    convert_count = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_engagement_user_cat", "user_id", "category", unique=True),
    )
