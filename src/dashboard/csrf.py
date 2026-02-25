"""CSRF protection middleware for cookie-based authentication."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response


# Path prefixes exempt from CSRF (auth endpoints and health check)
CSRF_EXEMPT_PREFIXES = (
    "/api/auth/",
    "/api/health",
)

# Safe HTTP methods that don't require CSRF
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class CSRFMiddleware(BaseHTTPMiddleware):
    """Validates CSRF tokens on state-changing requests using cookie-based auth.

    For POST/PUT/DELETE requests that use cookie auth (no Authorization header),
    requires a matching X-CSRF-Token header. The token value is set as a
    non-HttpOnly cookie so JavaScript can read and send it.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Safe methods never need CSRF
        if request.method in SAFE_METHODS:
            response = await call_next(request)
            return self._ensure_csrf_cookie(request, response)

        # Exempt paths (auth endpoints, health check)
        if request.url.path.startswith(CSRF_EXEMPT_PREFIXES):
            response = await call_next(request)
            return self._ensure_csrf_cookie(request, response)

        # If using Bearer token auth (Authorization header), skip CSRF
        # CSRF is only needed for cookie-based auth
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            return await call_next(request)

        # No cookie auth present — let the request through so auth
        # dependencies can return 401 as appropriate
        if "access_token" not in request.cookies:
            return await call_next(request)

        # Cookie-based auth: require CSRF token
        csrf_cookie = request.cookies.get("csrf_token")
        csrf_header = request.headers.get("x-csrf-token")

        if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
            from starlette.responses import JSONResponse

            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token missing or invalid"},
            )

        response = await call_next(request)
        return response

    def _ensure_csrf_cookie(self, request: Request, response: Response) -> Response:
        """Set a CSRF token cookie if one doesn't exist yet."""
        # Skip if request already has a csrf cookie or if the response already sets one
        if "csrf_token" in request.cookies:
            return response
        # Check if the response already sets the cookie (e.g. from login/register)
        for header_name, header_value in response.raw_headers:
            if header_name == b"set-cookie" and header_value.startswith(b"csrf_token="):
                return response
        token = secrets.token_urlsafe(32)
        response.set_cookie(
            key="csrf_token",
            value=token,
            httponly=False,  # Must be readable by JavaScript
            secure=True,
            samesite="strict",
            max_age=30 * 60,
            path="/",
        )
        return response
