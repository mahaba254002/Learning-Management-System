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
from app.services.payment_ledger import record_message
from app.services.subscriptions import REMINDER_DAYS, kenya_today, payment_instructions, subscription_view

SUBJECTS = {"due-soon": "Skynet subscription due on {due}", "overdue": "Skynet subscription overdue: access pauses on {freeze}",
            "frozen": "Skynet access paused: subscription unpaid"}


def how_to_pay(institution):
    pay = payment_instructions(institution)
    if not pay:
        return "<p>Reply to this email for payment details.</p>"
    if pay["kind"] == "TILL":
        steps = f"M-Pesa, Lipa na M-Pesa, Buy Goods and Services, till number <strong>{escape(pay['number'])}</strong>."
    else:
        steps = (f"M-Pesa, Lipa na M-Pesa, Pay Bill, business number <strong>{escape(pay['number'])}</strong>, "
                 f"account number <strong>{escape(pay['account'])}</strong>.")
    return f"<p>Pay by {steps}</p><p>Or sign in as administrator and use Pay with M-Pesa to receive a prompt on your phone.</p>"


def reminder_body(institution, row, state, stage):
    lead = {"due-soon": f"Your subscription for {escape(institution.name)} is due on {row.next_due_date}.",
            "overdue": f"Your subscription for {escape(institution.name)} was due on {row.next_due_date} and has not been paid. "
                       f"Access pauses on {state['freeze_date']} (Kenya time) unless payment is received.",
            "frozen": f"Access to Skynet for {escape(institution.name)} is paused because the subscription is unpaid. "
                      "Your records are kept safe. Access returns as soon as payment is received."}[stage]
    contact = f"<p>Questions: {escape(row.support_email)}</p>" if row.support_email else ""
    return f"<p>{lead}</p><p>Amount: <strong>KES {state['amount_due']:,.2f}</strong></p>{how_to_pay(institution)}{contact}"


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
        stage = "frozen" if state["frozen"] else "overdue" if today >= row.next_due_date else "due-soon" if today >= row.next_due_date - timedelta(days=REMINDER_DAYS) else None
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
        subject = SUBJECTS[stage].format(due=row.next_due_date, freeze=state["freeze_date"])
        body = reminder_body(institution, row, state, stage)
        try:
            db.flush()
            send_email(to=institution.official_email, subject=subject, html_body=body)
            notice.sent_at = datetime.now(timezone.utc)
            record_message(db, kind="REMINDER_EMAIL", direction="OUT", institution_id=row.institution_id, reference=key, amount=state["amount_due"],
                           summary=f"{subject} sent to {institution.official_email}", payload=dict(to=institution.official_email, subject=subject, html=body))
            db.commit()
            counts["sent"] += 1
        except (EmailSendError, IntegrityError):
            db.rollback()
            counts["failed"] += 1
    return counts
