"""
Password hashing and JWT helpers.

Concept note (JWT): a JSON Web Token is a string with three parts
(header.payload.signature). The payload is plain JSON — NOT encrypted, just
signed. Anyone can decode and read it, but nobody can modify it without
invalidating the signature, because the signature is computed using
JWT_SECRET_KEY, which only our server knows. This is why we can trust
institution_id/role embedded in a token we issued: if either value were
tampered with, the signature check would fail.
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.core.config import settings

# argon2 is the current recommended password hashing algorithm — resistant
# to GPU-based cracking in a way older algorithms (plain SHA-256, MD5) are
# not. We never store or compare raw passwords, only these hashes.
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(*, user_id: uuid.UUID, institution_id: uuid.UUID | None, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "institution_id": str(institution_id) if institution_id else None,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(*, user_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Raises jwt.PyJWTError (or a subclass) if invalid/expired/tampered."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])