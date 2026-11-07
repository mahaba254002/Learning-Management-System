"""Restricted operations a school admin asks the platform to carry out."""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import JSONType, Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin

REQUEST_KINDS = ('ACCOUNT_DELETION', 'PASSWORD_RESET', 'ACCOUNT_RECOVERY', 'INSTITUTION_CHANGE', 'OTHER')
REQUEST_STATUSES = ('PENDING', 'APPROVED', 'REJECTED', 'COMPLETED', 'WITHDRAWN')


class PlatformRequest(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = 'platform_requests'
    __table_args__ = (
        ForeignKeyConstraint(['institution_id', 'requested_by'], ['users.institution_id', 'users.id']),
        CheckConstraint("kind IN ('ACCOUNT_DELETION', 'PASSWORD_RESET', 'ACCOUNT_RECOVERY', 'INSTITUTION_CHANGE', 'OTHER')", name='ck_platform_requests_kind'),
        CheckConstraint("status IN ('PENDING', 'APPROVED', 'REJECTED', 'COMPLETED', 'WITHDRAWN')", name='ck_platform_requests_status'),
        Index('ix_platform_requests_queue', 'status', 'created_at'),
    )
    kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(10), default='PENDING')
    requested_by: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True))
    # The account the request is about, when there is one. Kept as a plain id:
    # the account may be anonymised by the request itself.
    target_user_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    target_label: Mapped[str] = mapped_column(String(200), default='')
    details: Mapped[str] = mapped_column(Text, default='')
    # Institution changes (field -> new value) or the new email for account recovery.
    changes: Mapped[dict] = mapped_column(JSONType, default=dict)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str] = mapped_column(String(1000), default='')
    completed_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
