"""
Reusable step-up verification: generate a short-lived, one-time code for a
sensitive action, email it (or for now, log it), and verify it later before
executing the actual action.

*** WHERE TO WIRE UP REAL EMAIL LATER ***
Search for `TODO: SEND EMAIL HERE` below. Right now it just prints to the
console so we can build and test the whole flow without email
infrastructure. When ready, replace that block with a call to your email
provider (Resend/Postmark/SES) instead of removing the surrounding logic.
"""

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.verification_code import VerificationCode, VerificationPurpose

CODE_LENGTH = 6
CODE_EXPIRY_MINUTES = 10
MAX_ATTEMPTS = 5


def generate_verification_code(
    *,
    db: Session,
    user_id: uuid.UUID,
    user_email: str | None,
    purpose: VerificationPurpose,
    payload: dict,
) -> uuid.UUID:
    """Creates a verification record and 'sends' the code. Returns the
    verification record's id, which the client must send back alongside
    the code to confirm the action."""

    # A random 6-digit numeric code, e.g. "042857". secrets.randbelow is
    # cryptographically secure — never use Python's plain `random` module
    # for anything security-related, it's predictable.
    raw_code = f"{secrets.randbelow(1_000_000):06d}"

    record = VerificationCode(
        user_id=user_id,
        purpose=purpose,
        code_hash=hash_password(raw_code),  # reuse the same argon2 hasher as passwords
        payload=payload,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=CODE_EXPIRY_MINUTES),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # TODO: SEND EMAIL HERE — replace this console log with a real email
    # send (e.g. Resend/Postmark/SES) to `user_email` once email
    # infrastructure is set up. Keep everything else in this function the
    # same; only this block changes.
    print(f"[VERIFICATION CODE] purpose={purpose.value} email={user_email} code={raw_code}")

    return record.id


class VerificationError(Exception):
    """Raised for any invalid/expired/already-used/wrong code."""


def confirm_verification_code(
    *,
    db: Session,
    verification_id: uuid.UUID,
    code: str,
    expected_user_id: uuid.UUID,
    expected_purpose: VerificationPurpose,
) -> dict:
    """Verifies the code and returns the stored payload if valid. Raises
    VerificationError otherwise. Marks the record consumed on success so it
    can never be replayed."""

    record = db.get(VerificationCode, verification_id)
    if record is None:
        raise VerificationError("Verification request not found")

    if record.user_id != expected_user_id:
        # Prevents one admin's pending action from being confirmed using
        # another admin's verification_id, even if guessed.
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