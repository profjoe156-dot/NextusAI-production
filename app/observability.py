import logging
import time
import uuid

from fastapi import Request
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware

HTTP_REQUESTS = Counter(
    "nexusai_http_requests_total", "HTTP requests", ["method", "path", "status"]
)
HTTP_DURATION = Histogram(
    "nexusai_http_request_duration_seconds", "HTTP request duration", ["method", "path"]
)
TELEGRAM_UPDATES = Counter("nexusai_telegram_updates_total", "Accepted Telegram webhook updates")
logger = logging.getLogger("nexusai.http")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))[:128]
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                },
            )
            raise
        elapsed = time.perf_counter() - started
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        HTTP_REQUESTS.labels(request.method, path, response.status_code).inc()
        HTTP_DURATION.labels(request.method, path).observe(elapsed)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response
