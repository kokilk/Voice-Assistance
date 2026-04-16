"""
Security headers middleware — applied to every response.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Prevent MIME-type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Block embedding in iframes
        response.headers["X-Frame-Options"] = "DENY"

        # Reduce referrer leakage
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Disable camera/mic/geolocation via Permissions-Policy
        response.headers["Permissions-Policy"] = (
            "camera=(), geolocation=()"
            # microphone intentionally omitted — browser Web Speech API needs it
        )

        # HSTS (only meaningful over HTTPS, harmless over HTTP)
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

        # Basic CSP — tightened for a single-origin local app
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "   # inline styles needed for dynamic state
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-src 'none'; "
            "object-src 'none';"
        )

        return response
