"""Discount 모델"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from database import Base


class Discount(Base):
    __tablename__ = "discounts"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    discount_type = Column(String(20), default="percent")
    discount_value = Column(Float, nullable=False)
    description = Column(Text, default="")
    min_purchase = Column(Integer, default=0)
    max_discount = Column(Integer, default=0)
    valid_from = Column(DateTime, default=datetime.utcnow)
    valid_until = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_discount_store_id", "store_id"),
        Index("idx_discount_company_id", "company_id"),
        Index("idx_discount_validity", "valid_from", "valid_until", "is_active"),
    )

    store = relationship("Store", back_populates="discounts")
    company = relationship("Company", back_populates="discounts")
