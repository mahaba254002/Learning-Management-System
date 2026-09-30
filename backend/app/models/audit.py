import uuid
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class AuditEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = 'audit_events'
    institution_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('institutions.id'), index=True, nullable=True)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), index=True)
    action: Mapped[str] = mapped_column(String(100))
    target_id: Mapped[str] = mapped_column(String(100))
    detail: Mapped[str] = mapped_column(String(500), default='')
