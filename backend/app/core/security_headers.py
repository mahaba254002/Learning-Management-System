"""
Security headers middleware — adds standard protective HTTP headers to
every response. These are cheap, well-established defaults recommended by
OWASP for any web application; none of them require frontend changes to
work, they're purely response headers the browser interprets.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        # HSTS only makes sense once served over HTTPS (which local dev
        # over http://localhost is not). We only add it outside
        # development so it doesn't cause confusing behavior locally.
        from app.core.config import settings

        if settings.ENVIRONMENT != "development":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"

        return response