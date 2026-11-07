"""Messages to parents and guardians by SMS (Africa's Talking) with a free email copy.

Every message is a draft until an institution admin sends it, answering their
own secret question. The answer is stored only as a hash. The platform pays for
SMS, so each institution has a monthly allowance the platform sets."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import JSONType, Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin

KINDS = ('RESULTS', 'FEES', 'ANNOUNCEMENT', 'EMERGENCY')


class MessagingSecret(TimestampMixin, TenantMixin, Base):
    """An institution admin's secret question and the hash of its answer."""
    __tablename__ = 'messaging_secrets'
    __table_args__ = (ForeignKeyConstraint(['institution_id', 'user_id'], ['users.institution_id', 'users.id'], ondelete='CASCADE'),)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    question: Mapped[str] = mapped_column(String(200))
    answer_hash: Mapped[str] = mapped_column(String(255))
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default='0')
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SmsAllowance(TimestampMixin, Base):
    """SMS parts an institution may send per calendar month (Nairobi time). Set by the platform."""
    __tablename__ = 'sms_allowances'
    institution_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey('institutions.id', ondelete='CASCADE'), primary_key=True)
    monthly_parts: Mapped[int] = mapped_column(Integer, default=0, server_default='0')
    __table_args__ = (CheckConstraint('monthly_parts >= 0 AND monthly_parts <= 1000000', name='ck_sms_allowances_parts'),)


class GuardianMessage(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = 'guardian_messages'
    __table_args__ = (
        UniqueConstraint('institution_id', 'id', name='uq_guardian_messages_tenant_id'),
        ForeignKeyConstraint(['institution_id', 'created_by'], ['users.institution_id', 'users.id']),
        ForeignKeyConstraint(['institution_id', 'sent_by'], ['users.institution_id', 'users.id']),
        CheckConstraint("kind IN ('RESULTS', 'FEES', 'ANNOUNCEMENT', 'EMERGENCY')", name='ck_guardian_messages_kind'),
        CheckConstraint("status IN ('DRAFT', 'SENDING', 'SENT', 'CANCELLED')", name='ck_guardian_messages_status'),
        Index('ix_guardian_messages_recent', 'institution_id', 'created_at'),
    )
    kind: Mapped[str] = mapped_column(String(12))
    title: Mapped[str] = mapped_column(String(160))
    # The text with placeholders such as {student} and {balance}.
    template: Mapped[str] = mapped_column(Text)
    # Who it goes to: class, term, exam, statuses, student list, all guardians or main contact only.
    audience: Mapped[dict] = mapped_column(JSONType, default=dict)
    status: Mapped[str] = mapped_column(String(10), default='DRAFT')
    created_by: Mapped[uuid.UUID] = mapped_column()
    sent_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MessageDelivery(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """One SMS or email to one guardian. The outbox and its history."""
    __tablename__ = 'message_deliveries'
    __table_args__ = (
        UniqueConstraint('institution_id', 'message_id', 'channel', 'address', 'student_id', name='uq_message_deliveries_once'),
        ForeignKeyConstraint(['institution_id', 'message_id'], ['guardian_messages.institution_id', 'guardian_messages.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['institution_id', 'student_id'], ['students.institution_id', 'students.id']),
        CheckConstraint("channel IN ('SMS', 'EMAIL')", name='ck_message_deliveries_channel'),
        CheckConstraint("status IN ('QUEUED', 'SENT', 'DELIVERED', 'FAILED')", name='ck_message_deliveries_status'),
        Index('ix_message_deliveries_queue', 'status', 'created_at'),
        Index('ix_message_deliveries_month', 'institution_id', 'channel', 'sent_at'),
    )
    message_id: Mapped[uuid.UUID] = mapped_column()
    student_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    guardian_name: Mapped[str] = mapped_column(String(160))
    channel: Mapped[str] = mapped_column(String(5))
    address: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    parts: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(10), default='QUEUED')
    provider_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    error: Mapped[str] = mapped_column(String(300), default='', server_default='')
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default='0')
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
