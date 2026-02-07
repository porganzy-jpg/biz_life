"""Company 모델"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date
from sqlalchemy.orm import relationship
from database import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    logo_url = Column(String(500), default="")
    is_active = Column(Boolean, default=True)
    employee_count = Column(Integer, default=0)
    industry = Column(String(100), default="")
    contract_start = Column(Date, nullable=True)
    contract_end = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    employees = relationship("User", back_populates="company")
    discounts = relationship("Discount", back_populates="company")
