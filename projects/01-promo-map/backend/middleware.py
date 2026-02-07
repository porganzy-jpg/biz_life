"""
PromoMap - 미들웨어
"""
import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("promomap")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration = round((time.time() - start) * 1000, 2)

        logger.info(
            f"{request.method} {request.url.path} "
            f"→ {response.status_code} ({duration}ms)"
        )
        return response
