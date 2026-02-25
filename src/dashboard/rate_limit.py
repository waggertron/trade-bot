"""Rate limiting middleware for the dashboard API."""

from __future__ import annotations

import hashlib
import time
from collections import defaultdict
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

if TYPE_CHECKING:
    from starlette.requests import Request


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token-bucket rate limiter per user/IP with separate read/write limits."""

    def __init__(
        self,
        app,
        read_limit: int = 100,
        write_limit: int = 10,
        window_seconds: int = 60,
    ) -> None:
        super().__init__(app)
        self._read_limit = read_limit
        self._write_limit = write_limit
        self._window = window_seconds
        # key -> list of timestamps
        self._read_requests: dict[str, list[float]] = defaultdict(list)
        self._write_requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next) -> Response:
        key = self._get_key(request)
        now = time.monotonic()
        is_write = request.method in ("POST", "PUT", "PATCH", "DELETE")

        if is_write:
            bucket = self._write_requests[key]
            limit = self._write_limit
        else:
            bucket = self._read_requests[key]
            limit = self._read_limit

        # Prune old entries
        cutoff = now - self._window
        bucket[:] = [t for t in bucket if t > cutoff]

        remaining = max(0, limit - len(bucket))

        if len(bucket) >= limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(cutoff + self._window)),
                    "Retry-After": str(self._window),
                },
            )

        bucket.append(now)
        remaining = max(0, limit - len(bucket))

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

    def _get_key(self, request: Request) -> str:
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer ") and len(auth) > 10:
            digest = hashlib.sha256(auth.encode()).hexdigest()
            return f"user:{digest}"
        client = request.client
        if client:
            return f"ip:{client.host}"
        return "unknown"
