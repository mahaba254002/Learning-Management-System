"""
CSRF protection via the double-submit cookie pattern.

Concept: the csrf_token cookie is deliberately NOT httpOnly — the frontend
JS must be able to read it and echo it back as a header. This is the whole
point: a malicious cross-site request can't read cookie values belonging to
our domain (browsers enforce this), so it can never produce a matching
header value, even though it CAN cause the browser to send our cookies
along automatically.
"""

import secrets

from fastapi import HTTPException, Request, status

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def verify_csrf(request: Request) -> None:
    if request.method in SAFE_METHODS:
        return

    cookie_value = request.cookies.get(CSRF_COOKIE_NAME)
    header_value = request.headers.get(CSRF_HEADER_NAME)

    if not cookie_value or not header_value or cookie_value != header_value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing or invalid",
        )