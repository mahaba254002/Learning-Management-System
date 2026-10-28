"""Access deadlines use Kenya's calendar, independent of a scheduler."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from app.models.subscription import Subscription
from app.core.config import settings


def kenya_today():
    return datetime.now(ZoneInfo("Africa/Nairobi")).date()


def subscription_view(row, today=None):
    today = today or kenya_today()
    if row is None:
        return dict(status="NOT_CONFIGURED", frozen=False, monthly_fee=0, grace_days=5, enforcement_enabled=False, manually_frozen=False, next_due_date=None, freeze_date=None, support_email=settings.BILLING_SUPPORT_EMAIL)
    freeze_date = row.next_due_date + timedelta(days=row.grace_days) if row.next_due_date else None
    overdue = bool(row.enforcement_enabled and freeze_date and today >= freeze_date)
    status = "FROZEN" if row.manually_frozen or overdue else "GRACE" if row.enforcement_enabled and row.next_due_date and today >= row.next_due_date else "CURRENT" if row.enforcement_enabled else "DISABLED"
    return dict(status=status, frozen=row.manually_frozen or overdue, monthly_fee=row.monthly_fee,
                grace_days=row.grace_days, enforcement_enabled=row.enforcement_enabled, manually_frozen=row.manually_frozen,
                next_due_date=row.next_due_date, freeze_date=freeze_date, support_email=row.support_email)


def check_subscription_access(db, institution_id):
    row = db.query(Subscription).filter(Subscription.institution_id == institution_id).first()
    state = subscription_view(row)
    if state["frozen"]:
        contact = f" Contact {state['support_email']} for assistance." if state['support_email'] else " Please contact the platform administrator."
        raise HTTPException(403, "Institution access is frozen due to its subscription status." + contact)
