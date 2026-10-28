"""Durable reminder keys; callers must run one scheduled worker.

Delivery is at least once: a process failure after email delivery but before the
commit may retry that notice. No notice is marked sent when delivery fails.
"""
from datetime import datetime, timedelta, timezone
from html import escape
from sqlalchemy.exc import IntegrityError
from app.models.institution import Institution, InstitutionStatus
from app.models.subscription import BillingNotice, Subscription
from app.services.email_service import EmailSendError, send_email
from app.services.subscriptions import kenya_today, subscription_view


def send_billing_reminders(db, *, deliver=False, today=None):
    today = today or kenya_today()
    counts = dict(due=0, sent=0, failed=0, missing_email=0)
    ids = [row[0] for row in db.query(Subscription.id).filter(Subscription.enforcement_enabled.is_(True), Subscription.next_due_date.is_not(None)).all()]
    for subscription_id in ids:
        row = db.query(Subscription).filter(Subscription.id == subscription_id).with_for_update(skip_locked=True).first()
        if row is None:
            continue
        institution = db.get(Institution, row.institution_id)
        if institution.status != InstitutionStatus.ACTIVE:
            db.rollback()
            continue
        state = subscription_view(row, today)
        stage = "frozen" if state["frozen"] else "overdue" if today >= row.next_due_date else "due-soon" if today >= row.next_due_date - timedelta(days=3) else None
        if stage is None:
            db.rollback()
            continue
        key = f"{row.next_due_date.isoformat()}:{stage}"
        notice = db.query(BillingNotice).filter_by(institution_id=row.institution_id, notice_key=key).first()
        if notice and notice.sent_at:
            db.rollback()
            continue
        counts["due"] += 1
        if not institution.official_email:
            counts["missing_email"] += 1
            db.rollback()
            continue
        if not deliver:
            db.rollback()
            continue
        if notice is None:
            notice = BillingNotice(institution_id=row.institution_id, notice_key=key)
            db.add(notice)
        try:
            db.flush()
            contact = escape(row.support_email)
            send_email(to=institution.official_email, subject=f"Skynet subscription: {stage}", html_body=
                f"<p>{escape(institution.name)} subscription payment is {stage}.</p>"
                f"<p>Amount: KES {row.monthly_fee}. Due: {row.next_due_date}. Access freeze date: {state['freeze_date']} (Kenya time).</p>"
                f"<p>Please contact {contact} for payment assistance.</p>")
            notice.sent_at = datetime.now(timezone.utc)
            db.commit()
            counts["sent"] += 1
        except (EmailSendError, IntegrityError):
            db.rollback()
            counts["failed"] += 1
    return counts
