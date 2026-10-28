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
import ipaddress
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
from app.core.workspace_access import resolve_workspace_target
from app.models.audit import AuditEvent
from app.models.pilot import AuthSession

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
    actor_user_id: uuid.UUID | None = None
    read_only: bool = False
    ip_address: str | None = None
    request_method: str | None = None
    request_path: str | None = None


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
    try:
        peer_ip = str(ipaddress.ip_address(request.client.host)) if request.client else None
    except ValueError:
        peer_ip = None
    metadata = dict(ip_address=peer_ip,
                    request_method=request.method, request_path=request.url.path[:500])

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

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise _unauthorized("Invalid authentication token")

    user = db.get(User, user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        raise _unauthorized("Account is no longer active")

    if payload.get('sid'):
        try:
            session = db.get(AuthSession, uuid.UUID(payload['sid']))
        except (TypeError, ValueError):
            raise _unauthorized()
        if not session or session.user_id != user.id or session.revoked:
            raise _unauthorized('Your session has ended. Please sign in again.')
        expiry = session.expires_at.replace(tzinfo=timezone.utc) if session.expires_at.tzinfo is None else session.expires_at
        if expiry <= datetime.now(timezone.utc): raise _unauthorized('Your session has ended. Please sign in again.')

    # If the password has been changed (self-service or admin-assisted)
    # since this token was issued, the token is dead — even if it hasn't
    # hit its normal 15-minute expiry yet. Without this, an old session
    # from before a reset keeps working, defeating the point of the reset.
    if user.password_changed_at is not None:
        issued_at = payload.get("iat")
        if issued_at is not None:
            issued_at_dt = datetime.fromtimestamp(issued_at, tz=timezone.utc)
            changed_at = user.password_changed_at
            if changed_at.tzinfo is None:
                changed_at = changed_at.replace(tzinfo=timezone.utc)
            if issued_at_dt < changed_at:
                raise _unauthorized("Session expired, please log in again")

    institution_id = user.institution_id

    if user.role != UserRole.PLATFORM_ADMIN and institution_id is None:
        raise _unauthorized("Your account is not assigned to an institution. Contact your administrator.")

    if institution_id is not None:
        institution = db.get(Institution, institution_id)
        if institution is None or institution.status != InstitutionStatus.ACTIVE:
            raise _unauthorized("Institution is no longer active")
        from app.services.subscriptions import check_subscription_access
        if request.url.path not in {"/api/me", "/api/auth/logout", "/api/auth/change-password", "/api/institution/subscription"}:
            check_subscription_access(db, institution_id)

    # Server-side enforcement of the forced password change. The frontend
    # redirect to /change-password is a UX nicety, not a security
    # boundary — without this check, a user with a temporary password
    # could call any other endpoint directly and skip changing it.
    if user.must_change_password and request.url.path not in ALLOWED_WHILE_PASSWORD_CHANGE_REQUIRED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must change your password before continuing.",
        )

    workspace_token = request.headers.get("X-Workspace-Token")
    if workspace_token:
        try:
            workspace = decode_token(workspace_token)
            if workspace.get("type") != "workspace" or workspace.get("sub") != str(user.id):
                raise _unauthorized("Invalid workspace access")
            target_id = uuid.UUID(workspace["target"])
        except (jwt.PyJWTError, KeyError, TypeError, ValueError):
            raise _unauthorized("Workspace access expired or invalid. Return to your own workspace.")
        target, read_only = resolve_workspace_target(db, user, target_id)
        mutation = request.method not in {"GET", "HEAD", "OPTIONS"}
        management = request.method == "POST" and request.url.path in {
            "/api/workspace-access/start", "/api/workspace-access/stop", "/api/auth/logout",
        }
        if request.url.path == "/api/auth/change-password":
            raise HTTPException(403, "Return to your own workspace to manage account credentials.")
        if read_only and mutation and not management:
            raise HTTPException(403, "This workspace is read-only. Changes are not permitted.")
        if mutation and not management:
            db.add(AuditEvent(actor_id=user.id, institution_id=target.institution_id,
                              action="workspace.mutation_attempt", target_id=str(target.id),
                              detail=f"{request.method} {request.url.path}"[:500], **metadata))
            db.commit()
        return AuthContext(user_id=target.id, institution_id=target.institution_id, role=target.role,
                           must_change_password=False, actor_user_id=user.id, read_only=read_only, **metadata)

    return AuthContext(
        user_id=user.id,
        institution_id=institution_id,
        role=user.role,
        must_change_password=user.must_change_password,
        **metadata,
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
