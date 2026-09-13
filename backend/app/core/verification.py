"""
Reusable step-up verification: generate a short-lived, one-time code for a
sensitive action, email it, and verify it later before executing the
actual action.

Sending is NOT best-effort. If the email fails to send, we roll back the
verification record we just created and raise VerificationError -- we
never want to tell an admin "check your email" when nothing was actually
sent. The failure itself is recorded in email_failures so a Super Admin
can see it (once the Audit Logs page is built).
"""

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.verification_code import VerificationCode, VerificationPurpose
from app.services.email_failure_service import record_email_failure
from app.services.email_service import EmailSendError, send_email

CODE_LENGTH = 6
CODE_EXPIRY_MINUTES = 10
MAX_ATTEMPTS = 5

_PURPOSE_SUBJECTS = {
    VerificationPurpose.CREATE_INSTITUTION: "Confirm: Create a new institution",
    VerificationPurpose.DELETE_INSTITUTION: "Confirm: Archive an institution",
    VerificationPurpose.PASSWORD_RESET: "Your password reset code",
}


class VerificationError(Exception):
    """Raised for any invalid/expired/already-used/wrong code, or when the
    verification email could not be sent."""


def generate_verification_code(
    *,
    db: Session,
    user_id: uuid.UUID,
    user_email: str | None,
    purpose: VerificationPurpose,
    payload: dict,
) -> uuid.UUID:
    if not user_email:
        raise VerificationError("This account has no email on file to send a code to")

    raw_code = f"{secrets.randbelow(1_000_000):06d}"

    record = VerificationCode(
        user_id=user_id,
        purpose=purpose,
        code_hash=hash_password(raw_code),
        payload=payload,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=CODE_EXPIRY_MINUTES),
    )
    db.add(record)
    db.flush()

    subject = _PURPOSE_SUBJECTS.get(purpose, "Your verification code")
    html_body = (
        "<p>Your verification code is:</p>"
        f'<h2 style="letter-spacing: 4px;">{raw_code}</h2>'
        f"<p>This code expires in {CODE_EXPIRY_MINUTES} minutes and can only be used once.</p>"
    )

    try:
        send_email(to=user_email, subject=subject, html_body=html_body)
    except EmailSendError as e:
        db.rollback()
        record_email_failure(
            db=db,
            recipient=user_email,
            subject=subject,
            email_type=purpose.value,
            error_message=str(e),
            context={"user_id": str(user_id)},
        )
        raise VerificationError(
            "We could not send the verification email. Please try again shortly."
        )

    db.commit()
    db.refresh(record)
    return record.id


def confirm_verification_code(
    *,
    db: Session,
    verification_id: uuid.UUID,
    code: str,
    expected_user_id: uuid.UUID,
    expected_purpose: VerificationPurpose,
) -> dict:
    record = db.get(VerificationCode, verification_id)
    if record is None:
        raise VerificationError("Verification request not found")

    if record.user_id != expected_user_id:
        raise VerificationError("Verification request not found")

    if record.purpose != expected_purpose:
        raise VerificationError("Verification request not found")

    if record.consumed_at is not None:
        raise VerificationError("This code has already been used")

    if datetime.now(timezone.utc) > record.expires_at:
        raise VerificationError("This code has expired, please request a new one")

    if record.attempt_count >= MAX_ATTEMPTS:
        raise VerificationError("Too many incorrect attempts, please request a new code")

    if not verify_password(code, record.code_hash):
        record.attempt_count += 1
        db.commit()
        raise VerificationError("Incorrect code")

    record.consumed_at = datetime.now(timezone.utc)
    db.commit()

    return record.payload