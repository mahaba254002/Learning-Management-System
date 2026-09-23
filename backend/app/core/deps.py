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
from datetime import datetime, timezone

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.csrf import verify_csrf
from app.core.security import decode_token
from app.db.session import get_db
from app.models.institution import Institution, InstitutionStatus
from app.models.user import User, UserRole, UserStatus

ACCESS_TOKEN_COOKIE_NAME = "access_token"

# Routes a user with must_change_password=True is still allowed to hit.
# Everything else is blocked with 403 until they change their password.
# Paths are matched against request.url.path exactly.
ALLOWED_WHILE_PASSWORD_CHANGE_REQUIRED = frozenset({
    "/api/auth/change-password",
    "/api/auth/logout",
    "/api/me",
})


@dataclass(frozen=True)
class AuthContext:
    user_id: uuid.UUID
    institution_id: uuid.UUID | None
    role: UserRole
    must_change_password: bool


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

    # If the password has been changed (self-service or admin-assisted)
    # since this token was issued, the token is dead — even if it hasn't
    # hit its normal 15-minute expiry yet. Without this, an old session
    # from before a reset keeps working, defeating the point of the reset.
    if user.password_changed_at is not None:
        issued_at = payload.get("iat")
        if issued_at is not None:
            issued_at_dt = datetime.fromtimestamp(issued_at, tz=timezone.utc)
            if issued_at_dt < user.password_changed_at:
                raise _unauthorized("Session expired, please log in again")

    institution_id = user.institution_id

    if institution_id is not None:
        institution = db.get(Institution, institution_id)
        if institution is None or institution.status != InstitutionStatus.ACTIVE:
            raise _unauthorized("Institution is no longer active")

    # Server-side enforcement of the forced password change. The frontend
    # redirect to /change-password is a UX nicety, not a security
    # boundary — without this check, a user with a temporary password
    # could call any other endpoint directly and skip changing it.
    if user.must_change_password and request.url.path not in ALLOWED_WHILE_PASSWORD_CHANGE_REQUIRED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must change your password before continuing.",
        )

    return AuthContext(
        user_id=user.id,
        institution_id=institution_id,
        role=user.role,
        must_change_password=user.must_change_password,
    )


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