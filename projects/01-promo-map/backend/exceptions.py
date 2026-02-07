"""
PromoMap - 커스텀 예외 + 핸들러
"""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse


class AppException(Exception):
    def __init__(self, status_code: int, detail: str, code: str = None):
        self.status_code = status_code
        self.detail = detail
        self.code = code


class NotFoundException(AppException):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(404, detail, "NOT_FOUND")


class DuplicateException(AppException):
    def __init__(self, detail: str = "Resource already exists"):
        super().__init__(409, detail, "DUPLICATE")


class UnauthorizedException(AppException):
    def __init__(self, detail: str = "Authentication required"):
        super().__init__(401, detail, "UNAUTHORIZED")


class ForbiddenException(AppException):
    def __init__(self, detail: str = "Access denied"):
        super().__init__(403, detail, "FORBIDDEN")


class BadRequestException(AppException):
    def __init__(self, detail: str = "Bad request"):
        super().__init__(400, detail, "BAD_REQUEST")


async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "code": "INTERNAL_ERROR"},
    )


def register_exception_handlers(app):
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
