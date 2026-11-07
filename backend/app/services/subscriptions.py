"""Access deadlines use Kenya's calendar, independent of a scheduler."""
import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from app.core.config import settings
from app.models.subscription import Subscription, SubscriptionPayment
from app.models.user import UserRole

GRACE_DAYS = 3
REMINDER_DAYS = 3
# Reachable by every signed-in user of a frozen institution.
FROZEN_OPEN_PATHS = {"/api/me", "/api/auth/logout", "/api/auth/change-password", "/api/institution/subscription", "/api/workspace-access/stop"}
FROZEN_ADMIN_PREFIX = "/api/institution/billing/"


def kenya_today():
    return datetime.now(ZoneInfo("Africa/Nairobi")).date()


def add_month(day):
    year, month = (day.year + 1, 1) if day.month == 12 else (day.year, day.month + 1)
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def amount_due(row, today=None):
    """What brings the institution up to date: every due date reached so far,
    or the next one when it falls inside the reminder window."""
    today = today or kenya_today()
    if not row or not row.enforcement_enabled or not row.next_due_date or not row.monthly_fee:
        return Decimal("0")
    periods, due = 0, row.next_due_date
    while due <= today:
        periods, due = periods + 1, add_month(due)
    if periods == 0 and today >= row.next_due_date - timedelta(days=REMINDER_DAYS):
        periods = 1
    return max(Decimal(row.monthly_fee) * periods - Decimal(row.credit_balance or 0), Decimal("0"))


def subscription_view(row, today=None):
    today = today or kenya_today()
    if row is None:
        return dict(status="NOT_CONFIGURED", frozen=False, monthly_fee=0, grace_days=GRACE_DAYS, enforcement_enabled=False, manually_frozen=False,
                    next_due_date=None, freeze_date=None, support_email=settings.BILLING_SUPPORT_EMAIL, credit_balance=0, amount_due=0, reminder=False)
    freeze_date = row.next_due_date + timedelta(days=GRACE_DAYS) if row.next_due_date else None
    overdue = bool(row.enforcement_enabled and freeze_date and today >= freeze_date)
    status = "FROZEN" if row.manually_frozen or overdue else "GRACE" if row.enforcement_enabled and row.next_due_date and today >= row.next_due_date else "CURRENT" if row.enforcement_enabled else "DISABLED"
    reminder = bool(row.enforcement_enabled and row.next_due_date and today >= row.next_due_date - timedelta(days=REMINDER_DAYS))
    return dict(status=status, frozen=row.manually_frozen or overdue, monthly_fee=row.monthly_fee,
                grace_days=GRACE_DAYS, enforcement_enabled=row.enforcement_enabled, manually_frozen=row.manually_frozen,
                next_due_date=row.next_due_date, freeze_date=freeze_date, support_email=row.support_email,
                credit_balance=row.credit_balance or 0, amount_due=amount_due(row, today), reminder=reminder)


def check_subscription_access(db, institution_id, role=None, path=""):
    if path in FROZEN_OPEN_PATHS or (role == UserRole.INSTITUTION_ADMIN and path.startswith(FROZEN_ADMIN_PREFIX)):
        return
    row = db.query(Subscription).filter(Subscription.institution_id == institution_id).first()
    if subscription_view(row)["frozen"]:
        raise HTTPException(403, "Institution access is frozen until the subscription is paid.")


def apply_payment(db, row, *, amount, reference, paid_on, source, recorded_by=None):
    """Credits money and moves the due date one month for each whole fee covered.
    The caller holds a lock on the subscription row and commits."""
    row.credit_balance = Decimal(row.credit_balance or 0) + Decimal(amount)
    previous = row.next_due_date
    if row.monthly_fee and row.next_due_date:
        while row.credit_balance >= row.monthly_fee:
            row.credit_balance -= Decimal(row.monthly_fee)
            row.next_due_date = add_month(row.next_due_date)
    payment = SubscriptionPayment(institution_id=row.institution_id, amount=amount, reference=reference, paid_on=paid_on, source=source,
                                  previous_due_date=previous, next_due_date=row.next_due_date or paid_on, recorded_by=recorded_by)
    db.add(payment)
    return payment


def payment_instructions(institution):
    from app.services import mpesa
    if not mpesa.configured():
        return None
    till = mpesa.is_till()
    return dict(method="MPESA", kind="TILL" if till else "PAYBILL", number=mpesa.pay_to_number(),
                account=None if till else institution.code)
