import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, JSONType, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin

PAYMENT_SOURCES = ('MANUAL', 'MPESA')
STK_STATUSES = ('PENDING', 'PAID', 'FAILED')


class Subscription(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "institution_subscriptions"
    __table_args__ = (UniqueConstraint("institution_id"), CheckConstraint("monthly_fee >= 0"), CheckConstraint("credit_balance >= 0"))
    monthly_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    next_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    enforcement_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    manually_frozen: Mapped[bool] = mapped_column(Boolean, default=False)
    support_email: Mapped[str] = mapped_column(String(255), default="")
    # M-Pesa money received that does not yet cover a whole month.
    credit_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)


class SubscriptionPayment(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "subscription_payments"
    __table_args__ = (UniqueConstraint("institution_id", "reference"), CheckConstraint("amount > 0"),
                      CheckConstraint("source IN ('MANUAL', 'MPESA')", name="ck_subscription_payments_source"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    reference: Mapped[str] = mapped_column(String(100))
    paid_on: Mapped[date] = mapped_column(Date)
    previous_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_due_date: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(10), default="MANUAL")
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class BillingNotice(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "billing_notices"
    __table_args__ = (UniqueConstraint("institution_id", "notice_key"),)
    notice_key: Mapped[str] = mapped_column(String(100))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MpesaStkRequest(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """A payment prompt sent to an administrator's phone."""
    __tablename__ = "mpesa_stk_requests"
    __table_args__ = (CheckConstraint("amount > 0"), CheckConstraint("status IN ('PENDING', 'PAID', 'FAILED')", name="ck_mpesa_stk_requests_status"))
    requested_by: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"))
    phone: Mapped[str] = mapped_column(String(12))
    amount: Mapped[int] = mapped_column(Integer)
    checkout_request_id: Mapped[str] = mapped_column(String(100), unique=True)
    merchant_request_id: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[str] = mapped_column(String(10), default="PENDING")
    result_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    result_description: Mapped[str] = mapped_column(String(255), default="")
    mpesa_receipt: Mapped[str | None] = mapped_column(String(30), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MpesaTransaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Money M-Pesa confirmed. Unmatched paybill payments have no institution until assigned."""
    __tablename__ = "mpesa_transactions"
    __table_args__ = (CheckConstraint("amount > 0"), CheckConstraint("channel IN ('STK', 'PAYBILL')", name="ck_mpesa_transactions_channel"))
    receipt: Mapped[str] = mapped_column(String(30), unique=True)
    institution_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(10))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    phone: Mapped[str] = mapped_column(String(20), default="")
    payer_name: Mapped[str] = mapped_column(String(150), default="")
    account_reference: Mapped[str] = mapped_column(String(40), default="")
    transacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PaymentMessage(Base):
    """Append-only evidence log. Each entry hashes the one before it, and the
    database refuses updates and deletes, so any tampering is detectable."""
    __tablename__ = "payment_messages"
    sequence: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    institution_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    direction: Mapped[str] = mapped_column(String(3))
    reference: Mapped[str] = mapped_column(String(100), default="", index=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    previous_hash: Mapped[str] = mapped_column(String(64))
    entry_hash: Mapped[str] = mapped_column(String(64), unique=True)
