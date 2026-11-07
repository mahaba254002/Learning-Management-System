"""Second check for platform admins: their own secret question.

Required to terminate or permanently delete an institution, export or back up
data, and restore a backup. Five wrong answers lock these actions for 30 minutes."""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.core.security import verify_password
from app.models.platform_secret import PlatformSecret
from app.services.audit_service import record_audit

MAX_FAILURES, LOCK_MINUTES = 5, 30


def normalise(answer):
    return ' '.join((answer or '').lower().split())


def check(db, ctx, answer, action):
    row = db.query(PlatformSecret).filter_by(user_id=ctx.user_id).with_for_update().first()
    if row is None:
        raise HTTPException(409, 'Set your secret question first (Platform → Settings)')
    now = datetime.now(timezone.utc)
    locked = row.locked_until.replace(tzinfo=timezone.utc) if row.locked_until and row.locked_until.tzinfo is None else row.locked_until
    if locked and locked > now:
        raise HTTPException(423, 'Too many wrong answers. Try again in 30 minutes.')
    if not verify_password(normalise(answer), row.answer_hash):
        row.failed_attempts += 1
        if row.failed_attempts >= MAX_FAILURES:
            row.failed_attempts, row.locked_until = 0, now + timedelta(minutes=LOCK_MINUTES)
        record_audit(db, ctx, 'platform.secret_failed', ctx.user_id, None, action)
        db.commit()
        raise HTTPException(403, 'That answer is not correct')
    row.failed_attempts, row.locked_until = 0, None
