from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Subscription(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "institution_subscriptions"
    __table_args__ = (UniqueConstraint("institution_id"), CheckConstraint("monthly_fee >= 0"), CheckConstraint("grace_days >= 0 AND grace_days <= 90"))
    monthly_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    next_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    grace_days: Mapped[int] = mapped_column(Integer, default=5)
    enforcement_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    manually_frozen: Mapped[bool] = mapped_column(Boolean, default=False)
    support_email: Mapped[str] = mapped_column(String(255), default="")


class SubscriptionPayment(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "subscription_payments"
    __table_args__ = (UniqueConstraint("institution_id", "reference"), CheckConstraint("amount > 0"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    reference: Mapped[str] = mapped_column(String(100))
    paid_on: Mapped[date] = mapped_column(Date)
    previous_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_due_date: Mapped[date] = mapped_column(Date)
    recorded_by: Mapped[str] = mapped_column(String(36))


class BillingNotice(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "billing_notices"
    __table_args__ = (UniqueConstraint("institution_id", "notice_key"),)
    notice_key: Mapped[str] = mapped_column(String(100))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
