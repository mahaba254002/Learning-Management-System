"""
Authentication routes.

Login/logout now work via httpOnly cookies instead of returning tokens in
the JSON response body. The CSRF token cookie is set alongside them,
readable by frontend JS so it can be echoed back as a header on mutating
requests (see app/core/csrf.py for the verification side).
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.csrf import CSRF_COOKIE_NAME, generate_csrf_token
from app.core.deps import AuthContext, get_current_context
from app.core.password_policy import PasswordPolicyError, validate_password_policy
from app.core.rate_limit import rate_limit
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.db.session import get_db
from app.models.institution import Institution, InstitutionStatus
from app.models.user import User, UserStatus
from app.models.verification_code import VerificationCode, VerificationPurpose
from app.core.verification import VerificationError, generate_verification_code
from app.schemas.auth import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LoginResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    UserSummary,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"


def _set_auth_cookies(response: Response, *, access_token: str, refresh_token: str) -> None:
    cookie_kwargs = dict(
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )

    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        **cookie_kwargs,
    )
    response.set_cookie(
        REFRESH_TOKEN_COOKIE,
        refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        **cookie_kwargs,
    )

    # CSRF cookie is deliberately NOT httponly — frontend JS must read it.
    response.set_cookie(
        CSRF_COOKIE_NAME,
        generate_csrf_token(),
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    dependencies=[Depends(rate_limit(max_requests=5, window_seconds=60, key_prefix="login"))],
)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.query(User).filter(User.username == payload.username).first()

    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid username or password",
    )

    if user is None:
        raise invalid_credentials

    if not verify_password(payload.password, user.password_hash):
        raise invalid_credentials

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not active. Contact your administrator.",
        )

    if user.institution_id is not None:
        institution = db.get(Institution, user.institution_id)
        if institution is None or institution.status != InstitutionStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your institution's account is not currently active.",
            )

    access_token = create_access_token(
        user_id=user.id, institution_id=user.institution_id, role=user.role.value
    )
    refresh_token = create_refresh_token(user_id=user.id)

    _set_auth_cookies(response, access_token=access_token, refresh_token=refresh_token)

    return LoginResponse(
        must_change_password=user.must_change_password,
        user=UserSummary.model_validate(user),
    )

@router.post("/logout")
def logout(response: Response, ctx: AuthContext = Depends(get_current_context)) -> dict:
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
    db.commit()

    return ChangePasswordResponse()

@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    dependencies=[Depends(rate_limit(max_requests=3, window_seconds=600, key_prefix="forgot-password"))],
)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> ForgotPasswordResponse:
    user = db.query(User).filter(User.email == payload.email).first()

    if user is not None and user.status == UserStatus.ACTIVE:
        try:
            generate_verification_code(
                db=db,
                user_id=user.id,
                user_email=user.email,
                purpose=VerificationPurpose.PASSWORD_RESET,
                payload={"user_id": str(user.id)},
            )
        except VerificationError:
            # We still return the generic success response even if sending
            # failed — this preserves the enumeration-safe behavior (never
            # reveal via this endpoint whether the account/email exists or
            # whether sending succeeded). The failure is already recorded
            # in email_failures for the Super Admin to see.
            pass

    return ForgotPasswordResponse()

@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=600, key_prefix="reset-password"))],
)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> ResetPasswordResponse:
    from datetime import datetime, timezone

    record = db.get(VerificationCode, payload.verification_id)
    if record is None or record.purpose != VerificationPurpose.PASSWORD_RESET:
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
    record.consumed_at = datetime.now(timezone.utc)
    db.commit()

    return ResetPasswordResponse()