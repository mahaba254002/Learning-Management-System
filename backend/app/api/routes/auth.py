"""
Authentication routes.

Login/logout work via httpOnly cookies instead of returning tokens in the
JSON response body. The CSRF token cookie is set alongside them, readable
by frontend JS so it can be echoed back as a header on mutating requests
(see app/core/csrf.py for the verification side).

Portal separation: platform/institution admins, teachers, and students
each log in through their own endpoint, even though all three share the
same `users` table and JWT/cookie mechanism. This is enforced here, not
just in the frontend routing, so an account of one kind cannot
authenticate through another portal's door. Every door returns the
identical error message for "wrong role for this door" and "wrong
password" so a username's role can't be discovered by testing which door
accepts it. The same separation applies to forgot/reset password.
"""

from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import uuid
import jwt

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.csrf import CSRF_COOKIE_NAME, generate_csrf_token, verify_csrf
from app.core.deps import AuthContext, get_current_context
from app.core.password_policy import PasswordPolicyError, validate_password_policy
from app.core.rate_limit import rate_limit
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.models.pilot import AuthSession
from app.db.session import get_db
from app.models.institution import Institution, InstitutionStatus
from app.models.user import User, UserRole, UserStatus
from app.models.verification_code import VerificationCode, VerificationPurpose
from app.core.verification import VerificationError, generate_verification_code
from app.schemas.auth import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    StudentLoginRequest,
    LoginResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    UserSummary,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"

# Compute once: unknown identities must perform one verification, like known ones.
_DUMMY_PASSWORD_HASH = hash_password("not-a-real-password")

# Three portals, three doors. Each set is disjoint from the others, and
# every user's role belongs to exactly one of them.
ADMIN_ROLES = frozenset({UserRole.PLATFORM_ADMIN, UserRole.INSTITUTION_ADMIN})
TEACHER_ROLES = frozenset({UserRole.TEACHER})
STUDENT_ROLES = frozenset({UserRole.STUDENT})


def _set_auth_cookies(response: Response, *, access_token: str, refresh_token: str, remember_me: bool = True) -> None:
    cookie_kwargs = dict(
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )

    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60 if remember_me else None,
        **cookie_kwargs,
    )
    response.set_cookie(
        REFRESH_TOKEN_COOKIE,
        refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60 if remember_me else None,
        **cookie_kwargs,
    )

    # CSRF cookie is deliberately NOT httponly — frontend JS must read it.
    response.set_cookie(
        CSRF_COOKIE_NAME,
        generate_csrf_token(),
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60 if remember_me else None,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def _bump_password_changed_at(user: User) -> None:
    """
    Stamps password_changed_at so that any access/refresh tokens issued
    before this moment are rejected by get_current_context, even if they
    haven't hit their normal expiry yet. Requires the
    users.password_changed_at column and the corresponding check in
    get_current_context.
    """
    user.password_changed_at = datetime.now(timezone.utc)


def _authenticate(
    payload: LoginRequest | StudentLoginRequest,
    response: Response,
    db: Session,
    *,
    allowed_roles: frozenset[UserRole],
) -> LoginResponse:
    """
    Shared login logic for every portal. `allowed_roles` is the enforcement
    point for portal separation: a user whose role is not in this set is
    rejected with the SAME error as a wrong password, so a login attempt
    can never be used to discover which door a given username belongs to.
    """
    if isinstance(payload, StudentLoginRequest) and payload.student_id:
        matches = db.query(User).filter(User.student_login_id == payload.student_id.upper(), User.student_login_method == "STUDENT_ID", User.role == UserRole.STUDENT).limit(2).all()
    else:
        query = db.query(User).filter(func.lower(User.email) == payload.email.lower())
        if isinstance(payload, StudentLoginRequest):
            query = query.filter(User.student_login_method == "EMAIL")
        matches = query.limit(2).all()
    # Refuse ambiguous email matches instead of selecting an arbitrary account.
    user = matches[0] if len(matches) == 1 else None

    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid sign-in details",
    )

    if user is None:
        # Run the password hasher anyway against a dummy hash so a
        # nonexistent username takes the same amount of time as a wrong
        # password for an existing one — otherwise response timing leaks
        # which usernames exist.
        verify_password(payload.password, _DUMMY_PASSWORD_HASH)
        raise invalid_credentials

    if not verify_password(payload.password, user.password_hash):
        raise invalid_credentials

    if user.role not in allowed_roles:
        # Deliberately identical to the wrong-password error above.
        raise invalid_credentials

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not active. Contact your administrator.",
        )

    if user.role != UserRole.PLATFORM_ADMIN and user.institution_id is None:
        raise HTTPException(status_code=403, detail="Your account is not assigned to an institution. Contact your administrator.")

    if user.institution_id is not None:
        institution = db.get(Institution, user.institution_id)
        if institution is None or institution.status != InstitutionStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your institution's account is not currently active.",
            )
        from app.services.subscriptions import check_subscription_access
        check_subscription_access(db, user.institution_id)

    session = AuthSession(id=uuid.uuid4(), user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        remember_me=payload.remember_me)
    access_token = create_access_token(
        user_id=user.id, institution_id=user.institution_id, role=user.role.value, session_id=session.id
    )
    refresh_token = create_refresh_token(user_id=user.id, session_id=session.id, expires_at=session.expires_at)
    session.refresh_digest = hashlib.sha256(refresh_token.encode()).hexdigest()
    db.add(session)
    db.commit()

    _set_auth_cookies(response, access_token=access_token, refresh_token=refresh_token, remember_me=payload.remember_me)
    response.headers["Cache-Control"] = "no-store"

    return LoginResponse(
        must_change_password=user.must_change_password,
        user=UserSummary.model_validate(user),
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    dependencies=[Depends(rate_limit(max_requests=5, window_seconds=60, key_prefix="login"))],
)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> LoginResponse:
    """Admin login door — platform admin, institution admin only.
    Teachers and students are rejected here; they have their own doors."""
    return _authenticate(payload, response, db, allowed_roles=ADMIN_ROLES)


@router.post(
    "/teacher/login",
    response_model=LoginResponse,
    dependencies=[Depends(rate_limit(max_requests=5, window_seconds=60, key_prefix="login"))],
)
def teacher_login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> LoginResponse:
    """Teacher login door. Admins and students are rejected here."""
    return _authenticate(payload, response, db, allowed_roles=TEACHER_ROLES)


@router.post(
    "/student/login",
    response_model=LoginResponse,
    dependencies=[Depends(rate_limit(max_requests=5, window_seconds=60, key_prefix="login"))],
)
def student_login(payload: StudentLoginRequest, response: Response, db: Session = Depends(get_db)) -> LoginResponse:
    """Student login door. Admins and teachers are rejected here."""
    return _authenticate(payload, response, db, allowed_roles=STUDENT_ROLES)


@router.post('/refresh', dependencies=[Depends(rate_limit(max_requests=60, window_seconds=60, key_prefix='refresh'))])
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    # This endpoint deliberately authenticates the real refresh cookie, never a delegated workspace.
    verify_csrf(request)
    invalid = HTTPException(401, 'Your session has ended. Please sign in again.')
    token = request.cookies.get(REFRESH_TOKEN_COOKIE, '')
    try:
        payload = decode_token(token)
        if payload.get('type') != 'refresh': raise ValueError()
        session_id, user_id = uuid.UUID(payload['sid']), uuid.UUID(payload['sub'])
        issued = datetime.fromtimestamp(payload['iat'], timezone.utc)
    except (jwt.PyJWTError, KeyError, TypeError, ValueError, OverflowError):
        raise invalid
    session = db.query(AuthSession).filter(AuthSession.id == session_id, AuthSession.user_id == user_id).with_for_update().first()
    if not session or session.revoked or not hmac.compare_digest(session.refresh_digest, hashlib.sha256(token.encode()).hexdigest()):
        raise invalid
    expiry = session.expires_at.replace(tzinfo=timezone.utc) if session.expires_at.tzinfo is None else session.expires_at
    user = db.get(User, user_id)
    if expiry <= datetime.now(timezone.utc) or not user or user.status != UserStatus.ACTIVE: raise invalid
    if user.password_changed_at:
        changed = user.password_changed_at.replace(tzinfo=timezone.utc) if user.password_changed_at.tzinfo is None else user.password_changed_at
        if issued < changed: raise invalid
    if user.role != UserRole.PLATFORM_ADMIN:
        institution = db.get(Institution, user.institution_id) if user.institution_id else None
        if not institution or institution.status != InstitutionStatus.ACTIVE: raise invalid
        from app.services.subscriptions import check_subscription_access
        check_subscription_access(db, institution.id)
    renewed = create_refresh_token(user_id=user.id, session_id=session.id, expires_at=expiry)
    session.refresh_digest = hashlib.sha256(renewed.encode()).hexdigest()
    db.commit()
    _set_auth_cookies(response, access_token=create_access_token(user_id=user.id, institution_id=user.institution_id,
        role=user.role.value, session_id=session.id), refresh_token=renewed, remember_me=session.remember_me)
    # Rotation never extends the original absolute expiry, including browser cookie lifetime.
    if session.remember_me:
        remaining = max(0, int((expiry - datetime.now(timezone.utc)).total_seconds()))
        response.set_cookie(REFRESH_TOKEN_COOKIE, renewed, max_age=remaining, httponly=True,
            secure=settings.cookie_secure, samesite='lax', path='/')
    return {'renewed': True}


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    verify_csrf(request)
    # Logout also works when access has expired or an institution has been suspended.
    try:
        token = decode_token(request.cookies.get(REFRESH_TOKEN_COOKIE, ''))
        if token.get('type') == 'refresh':
            row = db.get(AuthSession, uuid.UUID(token['sid']))
            if row and str(row.user_id) == token.get('sub'):
                row.revoked = True
                db.commit()
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        pass
    for cookie_name in (ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE, CSRF_COOKIE_NAME):
        response.delete_cookie(cookie_name, path="/")
    return {"message": "Logged out successfully."}


@router.post(
    "/change-password",
    response_model=ChangePasswordResponse,
    dependencies=[Depends(rate_limit(max_requests=5, window_seconds=300, key_prefix="change-password"))],
)
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(get_current_context),
) -> ChangePasswordResponse:
    """
    Shared across every role — the acting user is always determined from
    their own authenticated session (ctx.user_id), never a client-supplied
    ID, so no portal split is needed here: any role changes only their own
    password through this same logic.
    """
    user = db.get(User, ctx.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")

    try:
        validate_password_policy(payload.new_password)
    except PasswordPolicyError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if verify_password(payload.new_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from your current password",
        )

    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    _bump_password_changed_at(user)
    db.commit()

    return ChangePasswordResponse()


def _forgot_password(
    payload: ForgotPasswordRequest,
    db: Session,
    *,
    allowed_roles: frozenset[UserRole],
    reset_link_path: str,
) -> ForgotPasswordResponse:
    user = db.query(User).filter(func.lower(User.email) == payload.email.strip().lower()).first()

    if user is not None and user.role in allowed_roles and user.status == UserStatus.ACTIVE:
        try:
            generate_verification_code(
                db=db,
                user_id=user.id,
                user_email=user.email,
                purpose=VerificationPurpose.PASSWORD_RESET,
                # Recording the role lets the matching reset endpoint
                # refuse to redeem a code minted for a different portal,
                # even though all three portals share the same
                # VerificationPurpose.PASSWORD_RESET value.
                payload={"user_id": str(user.id), "role": user.role.value},
                reset_link_path=reset_link_path,
            )
        except VerificationError:
            # Still return the generic success response even if sending
            # failed — preserves enumeration-safe behavior (never reveal
            # via this endpoint whether the account/email exists or
            # whether sending succeeded). The failure is already recorded
            # in email_failures for the Super Admin to see.
            pass

    return ForgotPasswordResponse()


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    dependencies=[Depends(rate_limit(max_requests=3, window_seconds=600, key_prefix="forgot-password"))],
)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> ForgotPasswordResponse:
    """Admin forgot-password. A teacher or student email is treated as
    "not found" — same generic response either way, so no enumeration."""
    return _forgot_password(payload, db, allowed_roles=ADMIN_ROLES, reset_link_path="/reset-password")


@router.post(
    "/teacher/forgot-password",
    response_model=ForgotPasswordResponse,
    dependencies=[Depends(rate_limit(max_requests=3, window_seconds=600, key_prefix="teacher-forgot-password"))],
)
def teacher_forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> ForgotPasswordResponse:
    """Teacher forgot-password. An admin or student email is treated as
    "not found"."""
    return _forgot_password(payload, db, allowed_roles=TEACHER_ROLES, reset_link_path="/teacher/reset-password")


@router.post(
    "/student/forgot-password",
    response_model=ForgotPasswordResponse,
    dependencies=[Depends(rate_limit(max_requests=3, window_seconds=600, key_prefix="student-forgot-password"))],
)
def student_forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> ForgotPasswordResponse:
    """Student forgot-password. An admin or teacher email is treated as
    "not found"."""
    return _forgot_password(payload, db, allowed_roles=STUDENT_ROLES, reset_link_path="/student/reset-password")


def _reset_password(payload: ResetPasswordRequest, db: Session, *, allowed_roles: frozenset[UserRole]) -> ResetPasswordResponse:
    record = db.get(VerificationCode, payload.verification_id)
    if record is None or record.purpose != VerificationPurpose.PASSWORD_RESET:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset request")

    # Portal check: a code minted for one portal cannot be redeemed on a
    # different portal's reset endpoint. record.payload["role"] was
    # stamped in generate_verification_code above at request time. Codes
    # created before this field existed have no "role" key and are safely
    # rejected here (.get returns None, which matches no allowed role).
    if record.payload.get("role") not in {r.value for r in allowed_roles}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset request")

    if record.consumed_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This code has already been used")

    if datetime.now(timezone.utc) > record.expires_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This code has expired, please request a new one")

    if record.attempt_count >= 5:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Too many incorrect attempts, please request a new code")

    if not verify_password(payload.code, record.code_hash):
        record.attempt_count += 1
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect code")

    try:
        validate_password_policy(payload.new_password)
    except PasswordPolicyError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    user = db.get(User, record.payload["user_id"])
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset request")

    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    _bump_password_changed_at(user)
    record.consumed_at = datetime.now(timezone.utc)
    db.commit()

    return ResetPasswordResponse()


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=600, key_prefix="reset-password"))],
)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> ResetPasswordResponse:
    return _reset_password(payload, db, allowed_roles=ADMIN_ROLES)


@router.post(
    "/teacher/reset-password",
    response_model=ResetPasswordResponse,
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=600, key_prefix="teacher-reset-password"))],
)
def teacher_reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> ResetPasswordResponse:
    return _reset_password(payload, db, allowed_roles=TEACHER_ROLES)


@router.post(
    "/student/reset-password",
    response_model=ResetPasswordResponse,
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=600, key_prefix="student-reset-password"))],
)
def student_reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> ResetPasswordResponse:
    return _reset_password(payload, db, allowed_roles=STUDENT_ROLES)
