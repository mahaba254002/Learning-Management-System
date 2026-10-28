"""Issued academic documents retain their original academic and identity snapshot."""
import uuid
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class AcademicDocument(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = 'academic_documents'
    __table_args__ = (
        UniqueConstraint('institution_id', 'reference'),
        UniqueConstraint('institution_id', 'student_id', 'kind', 'source_digest'),
        ForeignKeyConstraint(['institution_id', 'student_id'], ['students.institution_id', 'students.id']),
        ForeignKeyConstraint(['institution_id', 'class_id'], ['academic_classes.institution_id', 'academic_classes.id']),
        CheckConstraint("kind IN ('REPORT_CARD', 'TRANSCRIPT')"),
        CheckConstraint("status IN ('ISSUED', 'REVOKED')"),
    )
    student_id: Mapped[uuid.UUID] = mapped_column(index=True)
    class_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    kind: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(10), default='ISSUED')
    reference: Mapped[str] = mapped_column(String(50))
    source_digest: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict] = mapped_column(JSON)
    issued_by_name: Mapped[str] = mapped_column(String(250))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
