"""공통 스키마"""
from pydantic import BaseModel
from typing import Optional

__all__ = ["MessageResponse", "ErrorResponse"]


class MessageResponse(BaseModel):
    status: str = "ok"
    message: str


class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None
