"""
Authentication + tenant-isolation dependencies.

*** This is the single most important file in the backend. ***

JWTs are now read from httpOnly cookies (set at login) instead of an
Authorization header. CSRF verification runs as part of this same
dependency for any mutating request, since every protected route already
depends on this function — one place, enforced everywhere, impossible to
forget on an individual route.
"""

import uuid
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.csrf import verify_csrf
from app.core.security import decode_token
from app.db.session import get_db
from app.models.institution import Institution, InstitutionStatus
from app.models.user import User, UserRole, UserStatus

ACCESS_TOKEN_COOKIE_NAME = "access_token"


@dataclass(frozen=True)
class AuthContext:
    user_id: uuid.UUID
    institution_id: uuid.UUID | None
    role: UserRole


def _unauthorized(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def get_current_context(
    request: Request,
    db: Session = Depends(get_db),
) -> AuthContext:
    # CSRF check runs first, before we even look at the JWT — a mutating
    # request with a missing/invalid CSRF token is rejected regardless of
    # whether the JWT itself is valid.
    verify_csrf(request)

    token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
    if token is None:
        raise _unauthorized("Missing authentication cookie")

    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Session expired, please log in again")
    except jwt.PyJWTError:
        raise _unauthorized("Invalid authentication token")

    if payload.get("type") != "access":
        raise _unauthorized("Invalid token type")

    user_id = uuid.UUID(payload["sub"])

    user = db.get(User, user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        raise _unauthorized("Account is no longer active")

    institution_id = user.institution_id

    if institution_id is not None:
        institution = db.get(Institution, institution_id)
        if institution is None or institution.status != InstitutionStatus.ACTIVE:
            raise _unauthorized("Institution is no longer active")

    return AuthContext(user_id=user.id, institution_id=institution_id, role=user.role)


def require_tenant_user(ctx: AuthContext = Depends(get_current_context)) -> AuthContext:
    if ctx.institution_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires an institution-scoped account",
        )
    return ctx


def require_platform_admin(ctx: AuthContext = Depends(get_current_context)) -> AuthContext:
    if ctx.role != UserRole.PLATFORM_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform administrator access required",
        )
    return ctx


def require_role(*allowed_roles: UserRole):
    def _check(ctx: AuthContext = Depends(require_tenant_user)) -> AuthContext:
        if ctx.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return ctx

    return _check