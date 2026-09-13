"""
Shared Redis connection.

Concept note: unlike SQLAlchemy's per-request Session, a Redis client is
safe to share as a single long-lived connection (it's not a transactional
database session, and Redis is fast enough that a shared connection pool
handles many requests without contention). We create it once, at import
time, and every module that needs Redis imports this same instance.
"""

import redis

from app.core.config import settings

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
