"""Requests to change an institution's grading after it was first set.

An institution admin sets grading once. After that, a change is a request the
platform administrator approves or rejects; the proposal and decision are kept."""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import JSONType, Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class GradingChangeRequest(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = 'grading_change_requests'
    __table_args__ = (
        CheckConstraint("status IN ('PENDING', 'APPROVED', 'REJECTED', 'WITHDRAWN')", name='ck_grading_change_requests_status'),
        Index('ix_grading_change_requests_status', 'status', 'created_at'),
    )
    proposed_rules: Mapped[dict] = mapped_column(JSONType)
    previous_rules: Mapped[dict] = mapped_column(JSONType)
    reason: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(10), default='PENDING')
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str] = mapped_column(String(1000), default='', server_default='')
