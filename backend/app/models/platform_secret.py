"""A platform admin's secret question, asked before destructive or data-export actions.

Only a hash of the answer is stored (argon2, like passwords)."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class PlatformSecret(TimestampMixin, Base):
    __tablename__ = 'platform_secrets'
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    question: Mapped[str] = mapped_column(String(200))
    answer_hash: Mapped[str] = mapped_column(String(255))
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default='0')
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
