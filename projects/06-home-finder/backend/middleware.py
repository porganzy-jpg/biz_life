"""
HomeFinder - 요청 로깅 미들웨어
"""
import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("homefinder.middleware")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        elapsed = (time.time() - start) * 1000
        if not request.url.path.startswith("/static"):
            logger.debug(
                f"{request.method} {request.url.path} -> {response.status_code} ({elapsed:.0f}ms)"
            )
        return response
