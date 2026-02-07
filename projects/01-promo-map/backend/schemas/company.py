"""기업 스키마"""
from pydantic import BaseModel
from typing import Optional

__all__ = ["CompanyResponse", "CompanyCreateRequest", "CompanyUpdateRequest"]


class CompanyResponse(BaseModel):
    id: int
    name: str
    code: str
    logo_url: str = ""
    is_active: bool = True
    employee_count: int = 0
    industry: str = ""
    contract_start: Optional[str] = None
    contract_end: Optional[str] = None

    class Config:
        from_attributes = True


class CompanyCreateRequest(BaseModel):
    name: str
    code: str
    logo_url: str = ""
    industry: str = ""
    employee_count: int = 0
    contract_start: Optional[str] = None
    contract_end: Optional[str] = None


class CompanyUpdateRequest(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    logo_url: Optional[str] = None
    is_active: Optional[bool] = None
    industry: Optional[str] = None
    employee_count: Optional[int] = None
    contract_start: Optional[str] = None
    contract_end: Optional[str] = None
