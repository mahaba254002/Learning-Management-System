"""
Simple Redis-backed rate limiting, used as a FastAPI dependency on
sensitive endpoints (login, verification code confirmation, password reset).

Concept: a "fixed window" rate limiter. For each (identifier, action) pair
(e.g. one IP address attempting login), we keep a counter in Redis that
expires automatically after `window_seconds`. Each request increments the
counter; if it exceeds `max_requests` before the window expires, we reject
with 429 Too Many Requests. This is simple and effective for our purposes;
more sophisticated (sliding window, token bucket) algorithms exist but add
complexity we don't need yet.

Development behavior: limits are multiplied by _DEV_MULTIPLIER when
ENVIRONMENT=development, so manual testing through /docs isn't blocked
mid-session. The real, strict values passed to rate_limit() at each call
site are the production-intended limits and are never changed for this —
only the runtime multiplier changes based on environment, so nothing needs
to be manually reverted before deploying.
"""

from fastapi import HTTPException, Request, status

from app.core.config import settings
from app.core.redis_client import redis_client

_DEV_MULTIPLIER = 20


def rate_limit(*, max_requests: int, window_seconds: int, key_prefix: str):
    """
    Factory returning a FastAPI dependency. Usage:
        Depends(rate_limit(max_requests=5, window_seconds=60, key_prefix="login"))

    Limits by client IP address. Good enough for now; could be extended to
    also limit by username/account later if needed.
    """

    effective_max = max_requests * _DEV_MULTIPLIER if settings.is_development else max_requests

    def _check(request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        redis_key = f"ratelimit:{key_prefix}:{client_ip}"

        # INCR atomically increments the counter (creating it at 1 if it
        # doesn't exist yet) — atomic matters here so concurrent requests
        # from the same IP can't race past each other and both slip through.
        current_count = redis_client.incr(redis_key)

        if current_count == 1:
            # This is the first request in a new window — set it to expire
            # after window_seconds, starting the clock on this window.
            redis_client.expire(redis_key, window_seconds)

        if current_count > effective_max:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests, please try again later.",
            )

    return _check