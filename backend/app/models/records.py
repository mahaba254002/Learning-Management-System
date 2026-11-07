"""Student records kept beside academics: guardians, fee status, discipline and announcements.

Fees are collected in the institution's own finance system. Skynet only keeps
the status and balance per term so staff know where a student stands."""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (Boolean, CheckConstraint, Date, ForeignKeyConstraint, Index, Numeric, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin

FEE_STATUSES = ('PAID', 'PARTIAL', 'UNPAID')
AUDIENCES = ('EVERYONE', 'STAFF', 'STUDENTS', 'CLASS')


class Guardian(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """A parent or guardian. Siblings share one row, matched on phone number."""
    __tablename__ = 'guardians'
    __table_args__ = (
        UniqueConstraint('institution_id', 'id', name='uq_guardians_tenant_id'),
        UniqueConstraint('institution_id', 'phone', name='uq_guardians_phone'),
    )
    full_name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    occupation: Mapped[str] = mapped_column(String(120), default='', server_default='')


class StudentGuardian(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = 'student_guardians'
    __table_args__ = (
        UniqueConstraint('institution_id', 'student_id', 'guardian_id', name='uq_student_guardians_pair'),
        ForeignKeyConstraint(['institution_id', 'student_id'], ['students.institution_id', 'students.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['institution_id', 'guardian_id'], ['guardians.institution_id', 'guardians.id'], ondelete='CASCADE'),
        Index('ix_student_guardians_guardian', 'institution_id', 'guardian_id'),
    )
    student_id: Mapped[uuid.UUID] = mapped_column(index=True)
    guardian_id: Mapped[uuid.UUID] = mapped_column()
    relationship: Mapped[str] = mapped_column(String(40))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')


class FeeStatus(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """Where a student stands on fees for one term or semester."""
    __tablename__ = 'student_fee_status'
    __table_args__ = (
        UniqueConstraint('institution_id', 'student_id', 'period_id', name='uq_student_fee_status_term'),
        ForeignKeyConstraint(['institution_id', 'student_id'], ['students.institution_id', 'students.id']),
        ForeignKeyConstraint(['institution_id', 'period_id'], ['academic_periods.institution_id', 'academic_periods.id']),
        ForeignKeyConstraint(['institution_id', 'updated_by'], ['users.institution_id', 'users.id']),
        CheckConstraint("status IN ('PAID', 'PARTIAL', 'UNPAID')", name='ck_student_fee_status_status'),
        CheckConstraint('balance >= 0', name='ck_student_fee_status_balance'),
        CheckConstraint("status <> 'PAID' OR balance = 0", name='ck_student_fee_status_paid_zero'),
        Index('ix_student_fee_status_period', 'institution_id', 'period_id', 'status'),
    )
    student_id: Mapped[uuid.UUID] = mapped_column(index=True)
    period_id: Mapped[uuid.UUID] = mapped_column()
    status: Mapped[str] = mapped_column(String(8))
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    note: Mapped[str] = mapped_column(String(300), default='', server_default='')
    updated_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)


class DisciplineRecord(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = 'discipline_records'
    __table_args__ = (
        ForeignKeyConstraint(['institution_id', 'student_id'], ['students.institution_id', 'students.id']),
        ForeignKeyConstraint(['institution_id', 'recorded_by'], ['users.institution_id', 'users.id']),
        Index('ix_discipline_records_student', 'institution_id', 'student_id', 'occurred_on'),
    )
    student_id: Mapped[uuid.UUID] = mapped_column()
    occurred_on: Mapped[date] = mapped_column(Date)
    category: Mapped[str] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(Text)
    action_taken: Mapped[str] = mapped_column(Text, default='', server_default='')
    recorded_by: Mapped[uuid.UUID] = mapped_column()


class Announcement(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = 'announcements'
    __table_args__ = (
        ForeignKeyConstraint(['institution_id', 'class_id'], ['academic_classes.institution_id', 'academic_classes.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['institution_id', 'created_by'], ['users.institution_id', 'users.id']),
        CheckConstraint("audience IN ('EVERYONE', 'STAFF', 'STUDENTS', 'CLASS')", name='ck_announcements_audience'),
        CheckConstraint("(audience = 'CLASS') = (class_id IS NOT NULL)", name='ck_announcements_class'),
        Index('ix_announcements_recent', 'institution_id', 'created_at'),
    )
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    audience: Mapped[str] = mapped_column(String(10))
    class_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column()
