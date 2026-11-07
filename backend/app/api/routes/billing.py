"""M-Pesa subscription payments and the platform payment evidence log."""
import csv
import hmac
import io
import json
import logging
import math
import uuid
from datetime import date, datetime, timedelta, timezone
from html import escape
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import Field, field_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.client_ip import client_ip
from app.core.config import settings
from app.core.deps import AuthContext, forbid_delegated_credentials, require_platform_admin, require_role
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.models.institution import Institution
from app.models.subscription import MpesaStkRequest, MpesaTransaction, PaymentMessage, Subscription
from app.models.user import UserRole
from app.schemas.academic import Input
from app.services import mpesa
from app.services.audit_service import record_audit
from app.services.email_service import EmailSendError, send_email
from app.services.payment_ledger import record_message, verify_chain
from app.services.subscriptions import amount_due, apply_payment, kenya_today, payment_instructions, subscription_view

router = APIRouter(prefix="/api", tags=["Billing"])
logger = logging.getLogger("app.billing")
institution_admin = require_role(UserRole.INSTITUTION_ADMIN)
NAIROBI = ZoneInfo("Africa/Nairobi")
MAX_MPESA_AMOUNT = 250000
PROMPT_TIMEOUT = timedelta(minutes=10)
ACCEPTED = {"ResultCode": 0, "ResultDesc": "Accepted"}


class PromptInput(Input):
    phone: str = Field(min_length=9, max_length=20)
    amount: int = Field(ge=1, le=MAX_MPESA_AMOUNT)

    @field_validator("phone")
    @classmethod
    def phone_number(cls, value):
        return mpesa.normalise_phone(value)


class AssignInput(Input):
    institution_id: uuid.UUID


def aware(value):
    return value if value is None or value.tzinfo else value.replace(tzinfo=timezone.utc)


def mpesa_time(value):
    try:
        return datetime.strptime(str(value), "%Y%m%d%H%M%S").replace(tzinfo=NAIROBI)
    except ValueError:
        return datetime.now(timezone.utc)


def prompt_view(row):
    return dict(id=row.id, status=row.status, amount=row.amount, phone=row.phone[:6] + "***" + row.phone[-3:],
                result_description=row.result_description, mpesa_receipt=row.mpesa_receipt, created_at=row.created_at)


def send_receipt(db, institution, txn, row):
    if not institution.official_email:
        return
    subject = f"Skynet payment received: KES {txn.amount:,.2f}"
    body = (f"<p>We received KES {txn.amount:,.2f} for {escape(institution.name)}. M-Pesa receipt {escape(txn.receipt)}.</p>"
            f"<p>Subscription paid until {row.next_due_date}.</p>")
    try:
        send_email(to=institution.official_email, subject=subject, html_body=body)
    except EmailSendError:
        return
    record_message(db, kind="RECEIPT_EMAIL", direction="OUT", institution_id=institution.id, reference=txn.receipt, amount=txn.amount,
                   summary=f"Payment receipt sent to {institution.official_email}", payload=dict(to=institution.official_email, subject=subject, html=body))
    db.commit()


def settle(db, txn, institution_id, actor=None):
    """Applies confirmed money to a subscription. The caller has flushed txn."""
    institution = db.query(Institution).filter(Institution.id == institution_id).with_for_update().one()
    row = db.query(Subscription).filter(Subscription.institution_id == institution_id).with_for_update().first()
    txn.institution_id = institution_id
    if row is None or not row.next_due_date:
        record_message(db, kind="PAYMENT_UNAPPLIED", direction="SYS", institution_id=institution_id, reference=txn.receipt, amount=txn.amount,
                       summary="Payment received but the subscription is not configured; apply it manually")
        db.commit()
        return
    before = row.next_due_date
    paid_on = (aware(txn.transacted_at) or datetime.now(timezone.utc)).astimezone(NAIROBI).date()
    apply_payment(db, row, amount=txn.amount, reference=txn.receipt, paid_on=paid_on, source="MPESA", recorded_by=actor)
    txn.applied_at = datetime.now(timezone.utc)
    record_message(db, kind="PAYMENT_APPLIED", direction="SYS", institution_id=institution_id, reference=txn.receipt, amount=txn.amount,
                   summary=f"M-Pesa {txn.receipt} applied. Due date {before} moved to {row.next_due_date}; credit KES {row.credit_balance}",
                   payload=dict(channel=txn.channel, previous_due_date=str(before), next_due_date=str(row.next_due_date), credit_balance=str(row.credit_balance)))
    db.commit()
    send_receipt(db, institution, txn, row)


def confirm_prompt(db, prompt):
    """Asks Safaricom for the result of a prompt; forged callbacks never move money on their own."""
    try:
        result = mpesa.stk_query(prompt.checkout_request_id)
    except mpesa.MpesaError:
        db.rollback()
        return
    record_message(db, kind="STK_QUERY", direction="IN", institution_id=prompt.institution_id, reference=prompt.checkout_request_id,
                   amount=prompt.amount, summary=f"Status check: {result.get('ResultDesc') or result.get('errorMessage') or 'no answer'}", payload=result)
    code = result.get("ResultCode")
    if code is None:
        if datetime.now(timezone.utc) - aware(prompt.created_at) > PROMPT_TIMEOUT:
            prompt.status, prompt.result_description = "FAILED", "No answer from M-Pesa"
            prompt.completed_at = datetime.now(timezone.utc)
        db.commit()
        return
    prompt.result_code, prompt.result_description = str(code), str(result.get("ResultDesc", ""))[:255]
    prompt.completed_at = datetime.now(timezone.utc)
    if str(code) != "0":
        prompt.status = "FAILED"
        db.commit()
        return
    prompt.status = "PAID"
    receipt = prompt.mpesa_receipt or f"STK:{prompt.checkout_request_id}"[:30]
    txn = MpesaTransaction(receipt=receipt, channel="STK", amount=prompt.amount, phone=prompt.phone, account_reference="",
                           transacted_at=datetime.now(timezone.utc))
    db.add(txn)
    db.flush()
    settle(db, txn, prompt.institution_id, prompt.requested_by)


def callback_guard(secret, request):
    expected = settings.MPESA_CALLBACK_SECRET
    if not expected or not hmac.compare_digest(secret.encode(), expected.encode()):
        raise HTTPException(404, "Not found")
    allowed = {ip.strip() for ip in settings.MPESA_ALLOWED_IPS.split(",") if ip.strip()}
    if allowed and client_ip(request) not in allowed:
        raise HTTPException(404, "Not found")


async def callback_body(request):
    try:
        body = json.loads(await request.body() or b"{}")
    except ValueError:
        body = {}
    return body if isinstance(body, dict) else {}


@router.post("/institution/billing/mpesa/prompt", status_code=201, dependencies=[Depends(forbid_delegated_credentials), Depends(rate_limit(max_requests=5, window_seconds=300, key_prefix="mpesa-prompt"))])
def start_prompt(body: PromptInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(institution_admin)):
    if not mpesa.configured():
        raise HTTPException(503, "M-Pesa payments are not set up yet. Contact the platform administrator.")
    institution = db.query(Institution).filter(Institution.id == ctx.institution_id).with_for_update().one()
    recent = db.query(MpesaStkRequest).filter(MpesaStkRequest.institution_id == ctx.institution_id, MpesaStkRequest.status == "PENDING",
                                              MpesaStkRequest.created_at >= datetime.now(timezone.utc) - timedelta(minutes=2)).first()
    if recent:
        raise HTTPException(409, "A payment prompt was sent less than two minutes ago. Check your phone or wait before trying again.")
    try:
        result = mpesa.stk_push(phone=body.phone, amount=body.amount, account_reference=institution.code, description="Subscription")
    except mpesa.MpesaError as exc:
        raise HTTPException(502, str(exc))
    if str(result.get("ResponseCode")) != "0" or not result.get("CheckoutRequestID"):
        record_message(db, kind="STK_REJECTED", direction="IN", institution_id=institution.id, amount=body.amount,
                       summary=f"M-Pesa refused the prompt: {result.get('errorMessage') or result.get('ResponseDescription') or 'unknown reason'}", payload=result)
        db.commit()
        raise HTTPException(502, "M-Pesa could not send the prompt. Check the number and try again.")
    prompt = MpesaStkRequest(institution_id=institution.id, requested_by=ctx.actor_user_id or ctx.user_id, phone=body.phone, amount=body.amount,
                             checkout_request_id=result["CheckoutRequestID"], merchant_request_id=result.get("MerchantRequestID", ""))
    db.add(prompt)
    record_message(db, kind="STK_PROMPT", direction="OUT", institution_id=institution.id, reference=prompt.checkout_request_id, amount=body.amount,
                   summary=f"Payment prompt for KES {body.amount} sent to {prompt_view(prompt)['phone']}", payload=dict(request=dict(phone=body.phone, amount=body.amount), response=result))
    record_audit(db, ctx, "subscription.mpesa_prompt", institution.id, institution.id, f"KES {body.amount}")
    db.commit()
    return prompt_view(prompt)


@router.get("/institution/billing/mpesa/prompt/{prompt_id}", dependencies=[Depends(rate_limit(max_requests=60, window_seconds=60, key_prefix="mpesa-poll"))])
def prompt_status(prompt_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(institution_admin)):
    prompt = db.query(MpesaStkRequest).filter(MpesaStkRequest.id == prompt_id, MpesaStkRequest.institution_id == ctx.institution_id).with_for_update().first()
    if not prompt:
        raise HTTPException(404, "Payment prompt not found")
    if prompt.status == "PENDING" and datetime.now(timezone.utc) - aware(prompt.created_at) > timedelta(seconds=20):
        confirm_prompt(db, prompt)
    db.refresh(prompt)
    row = db.query(Subscription).filter(Subscription.institution_id == ctx.institution_id).first()
    return dict(**prompt_view(prompt), subscription=subscription_view(row))


@router.post("/payments/mpesa/{secret}/stk-callback")
async def stk_callback(secret: str, request: Request, db: Session = Depends(get_db)):
    callback_guard(secret, request)
    body = await callback_body(request)
    data = (body.get("Body") or {}).get("stkCallback") or {}
    checkout = str(data.get("CheckoutRequestID", ""))[:100]
    prompt = db.query(MpesaStkRequest).filter(MpesaStkRequest.checkout_request_id == checkout).with_for_update().first() if checkout else None
    items = {item.get("Name"): item.get("Value") for item in (data.get("CallbackMetadata") or {}).get("Item", []) if isinstance(item, dict)}
    record_message(db, kind="STK_CALLBACK", direction="IN", institution_id=prompt.institution_id if prompt else None, reference=checkout,
                   amount=items.get("Amount"), summary=f"M-Pesa callback: {data.get('ResultDesc', 'no description')}", payload=body)
    db.commit()
    if not prompt:
        return ACCEPTED
    prompt = db.query(MpesaStkRequest).filter(MpesaStkRequest.id == prompt.id).with_for_update().one()
    receipt = str(items.get("MpesaReceiptNumber") or "")[:30]
    if prompt.status == "PAID" and receipt:
        txn = db.query(MpesaTransaction).filter(MpesaTransaction.receipt == f"STK:{checkout}"[:30]).first()
        if txn:
            txn.receipt, prompt.mpesa_receipt = receipt, receipt
        db.commit()
        return ACCEPTED
    if prompt.status != "PENDING":
        db.commit()
        return ACCEPTED
    if str(data.get("ResultCode")) != "0":
        prompt.status, prompt.result_code = "FAILED", str(data.get("ResultCode"))
        prompt.result_description = str(data.get("ResultDesc", ""))[:255]
        prompt.completed_at = datetime.now(timezone.utc)
        db.commit()
        return ACCEPTED
    prompt.mpesa_receipt = receipt or None
    db.flush()
    confirm_prompt(db, prompt)
    return ACCEPTED


def institution_for_account(db, account):
    account = (account or "").strip().upper()
    return db.query(Institution).filter(func.upper(Institution.code) == account).first() if account else None


@router.post("/payments/mpesa/{secret}/c2b-validation")
async def paybill_validation(secret: str, request: Request, db: Session = Depends(get_db)):
    callback_guard(secret, request)
    body = await callback_body(request)
    institution = institution_for_account(db, body.get("BillRefNumber"))
    accepted = institution is not None
    record_message(db, kind="PAYBILL_VALIDATION", direction="IN", institution_id=institution.id if institution else None,
                   reference=str(body.get("TransID", "")), amount=body.get("TransAmount"),
                   summary=f"Paybill account '{body.get('BillRefNumber', '')}' {'accepted' if accepted else 'rejected: no such institution'}", payload=body)
    db.commit()
    return {"ResultCode": "0", "ResultDesc": "Accepted"} if accepted else {"ResultCode": "C2B00012", "ResultDesc": "Rejected"}


@router.post("/payments/mpesa/{secret}/c2b-confirmation")
async def paybill_confirmation(secret: str, request: Request, db: Session = Depends(get_db)):
    callback_guard(secret, request)
    body = await callback_body(request)
    receipt = str(body.get("TransID", "")).strip()[:30]
    institution = institution_for_account(db, body.get("BillRefNumber"))
    record_message(db, kind="PAYBILL_CONFIRMATION", direction="IN", institution_id=institution.id if institution else None, reference=receipt,
                   amount=body.get("TransAmount"), summary=f"Paybill payment to account '{body.get('BillRefNumber', '')}'", payload=body)
    db.commit()
    try:
        amount = round(float(body.get("TransAmount")), 2)
    except (TypeError, ValueError):
        amount = 0
    if not receipt or amount <= 0 or str(body.get("BusinessShortCode", "")) != mpesa.pay_to_number():
        return ACCEPTED
    if db.query(MpesaTransaction).filter(MpesaTransaction.receipt == receipt).first():
        return ACCEPTED
    name = " ".join(str(body.get(key, "")) for key in ("FirstName", "MiddleName", "LastName")).split()
    txn = MpesaTransaction(receipt=receipt, channel="PAYBILL", amount=amount, phone=str(body.get("MSISDN", ""))[:20], payer_name=" ".join(name)[:150],
                           account_reference=str(body.get("BillRefNumber", ""))[:40], transacted_at=mpesa_time(body.get("TransTime")))
    db.add(txn)
    db.flush()
    if institution:
        settle(db, txn, institution.id)
    else:
        record_message(db, kind="PAYMENT_UNMATCHED", direction="SYS", reference=receipt, amount=amount,
                       summary=f"Account '{txn.account_reference}' matches no institution; assign it from the payments page")
        db.commit()
    return ACCEPTED


def message_query(db, institution_id, kind, search, date_from, date_to):
    query = db.query(PaymentMessage)
    if institution_id: query = query.filter(PaymentMessage.institution_id == institution_id)
    if kind: query = query.filter(PaymentMessage.kind == kind)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(PaymentMessage.reference.ilike(term), PaymentMessage.summary.ilike(term)))
    if date_from: query = query.filter(PaymentMessage.created_at >= datetime.combine(date_from, datetime.min.time(), NAIROBI))
    if date_to: query = query.filter(PaymentMessage.created_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time(), NAIROBI))
    return query


def institution_names(db, ids):
    ids = {i for i in ids if i}
    return {row.id: (row.name, row.code) for row in db.query(Institution).filter(Institution.id.in_(ids))} if ids else {}


def message_view(row, names):
    name, code = names.get(row.institution_id, (None, None))
    return dict(sequence=row.sequence, created_at=row.created_at, institution_id=row.institution_id, institution_name=name, institution_code=code,
                kind=row.kind, direction=row.direction, reference=row.reference, amount=row.amount, summary=row.summary, entry_hash=row.entry_hash)


@router.get("/platform/payment-messages")
def payment_messages(institution_id: uuid.UUID | None = None, kind: str = Query("", max_length=40), search: str = Query("", max_length=100),
                     date_from: date | None = None, date_to: date | None = None, offset: int = Query(0, ge=0),
                     db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    query = message_query(db, institution_id, kind, search, date_from, date_to)
    rows = query.order_by(PaymentMessage.sequence.desc()).offset(offset).limit(50).all()
    names = institution_names(db, [row.institution_id for row in rows])
    kinds = [k for (k,) in db.query(PaymentMessage.kind).distinct().order_by(PaymentMessage.kind)]
    return dict(total=query.count(), kinds=kinds, items=[message_view(row, names) for row in rows])


@router.get("/platform/payment-messages/verify")
def verify_messages(db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    return verify_chain(db)


def safe_cell(value):
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@router.get("/platform/payment-messages/export")
def export_messages(institution_id: uuid.UUID | None = None, kind: str = Query("", max_length=40), search: str = Query("", max_length=100),
                    date_from: date | None = None, date_to: date | None = None,
                    db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    rows = message_query(db, institution_id, kind, search, date_from, date_to).order_by(PaymentMessage.sequence).all()
    names = institution_names(db, [row.institution_id for row in rows])
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["sequence", "created_at_utc", "institution", "code", "kind", "direction", "reference", "amount_kes", "summary", "payload", "previous_hash", "entry_hash"])
    for row in rows:
        name, code = names.get(row.institution_id, ("", ""))
        writer.writerow([safe_cell(v) for v in (row.sequence, aware(row.created_at).isoformat(), name, code, row.kind, row.direction, row.reference,
                                                 row.amount, row.summary, json.dumps(row.payload, sort_keys=True), row.previous_hash, row.entry_hash)])
    record_audit(db, ctx, "billing.messages_exported", None, None, f"{len(rows)} entries")
    db.commit()
    stamp = kenya_today().isoformat()
    return StreamingResponse(iter([out.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="skynet-payment-messages-{stamp}.csv"'})


@router.get("/platform/payment-messages/{sequence}")
def payment_message(sequence: int, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    row = db.get(PaymentMessage, sequence)
    if not row:
        raise HTTPException(404, "Entry not found")
    return dict(**message_view(row, institution_names(db, [row.institution_id])), payload=row.payload, previous_hash=row.previous_hash)


@router.get("/platform/mpesa")
def mpesa_status(db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    unmatched = db.query(MpesaTransaction).filter(MpesaTransaction.institution_id.is_(None)).order_by(MpesaTransaction.created_at.desc()).limit(100).all()
    return dict(configured=mpesa.configured(), environment=settings.MPESA_ENVIRONMENT, kind="TILL" if mpesa.is_till() else "PAYBILL",
                number=mpesa.pay_to_number(), unmatched=[dict(id=t.id, receipt=t.receipt, amount=t.amount, phone=t.phone, payer_name=t.payer_name,
                account_reference=t.account_reference, transacted_at=t.transacted_at) for t in unmatched])


@router.post("/platform/mpesa/register-paybill", dependencies=[Depends(forbid_delegated_credentials)])
def register_paybill(db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    if not mpesa.configured() or mpesa.is_till():
        raise HTTPException(409, "Paybill registration needs Daraja keys and a paybill number")
    try:
        result = mpesa.register_paybill_urls()
    except mpesa.MpesaError as exc:
        raise HTTPException(502, str(exc))
    record_message(db, kind="PAYBILL_REGISTERED", direction="OUT", summary=f"Paybill callback addresses registered: {result.get('ResponseDescription', '')}", payload=result)
    record_audit(db, ctx, "billing.paybill_registered", None, None)
    db.commit()
    return result


@router.post("/platform/mpesa/transactions/{transaction_id}/assign", dependencies=[Depends(forbid_delegated_credentials)])
def assign_transaction(transaction_id: uuid.UUID, body: AssignInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    txn = db.query(MpesaTransaction).filter(MpesaTransaction.id == transaction_id).with_for_update().first()
    if not txn or txn.institution_id:
        raise HTTPException(409, "This payment is already assigned")
    if not db.get(Institution, body.institution_id):
        raise HTTPException(404, "Institution not found")
    record_message(db, kind="PAYMENT_ASSIGNED", direction="SYS", institution_id=body.institution_id, reference=txn.receipt, amount=txn.amount,
                   summary=f"Unmatched payment {txn.receipt} assigned by platform administrator")
    record_audit(db, ctx, "billing.payment_assigned", txn.id, body.institution_id, txn.receipt)
    settle(db, txn, body.institution_id, ctx.actor_user_id or ctx.user_id)
    return mpesa_status(db, ctx)


def billing_extras(db, institution):
    row = db.query(Subscription).filter(Subscription.institution_id == institution.id).first()
    due = amount_due(row)
    return dict(payment=payment_instructions(institution), suggested_amount=min(math.ceil(due), MAX_MPESA_AMOUNT) if due else 0)
