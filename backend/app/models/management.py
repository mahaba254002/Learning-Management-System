"""One HR record per employee. A login (users row) is optional and linked by user_id.

This replaces the old teachers table, which is kept in the database for one
release but no longer read."""
import uuid
from datetime import date
from sqlalchemy import CheckConstraint, Date, ForeignKey, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class StaffMember(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = 'staff_members'
    __table_args__ = (
        UniqueConstraint('institution_id', 'id'), UniqueConstraint('institution_id', 'staff_number'),
        UniqueConstraint('institution_id', 'user_id'),
        ForeignKeyConstraint(['institution_id', 'department_id'], ['academic_departments.institution_id', 'academic_departments.id']),
        ForeignKeyConstraint(['institution_id', 'user_id'], ['users.institution_id', 'users.id']),
        CheckConstraint("category IN ('TEACHING','NON_TEACHING')"),
        CheckConstraint("status IN ('ACTIVE','ON_LEAVE','INACTIVE')"),
        CheckConstraint("employment_type IN ('FULL_TIME','PART_TIME','CONTRACT','VOLUNTEER')"),
        CheckConstraint("gender IS NULL OR gender IN ('MALE','FEMALE','OTHER','PREFER_NOT_TO_SAY')", name='ck_staff_members_gender'),
    )
    staff_number: Mapped[str] = mapped_column(String(40))
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(15))
    job_title: Mapped[str] = mapped_column(String(120))
    department_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    employment_type: Mapped[str] = mapped_column(String(15), default='FULL_TIME')
    status: Mapped[str] = mapped_column(String(10), default='ACTIVE')
    joined_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    qualification: Mapped[str | None] = mapped_column(String(255), nullable=True)
    specialization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invitation_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey('invitations.id'), nullable=True)


class StaffAttendance(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = 'staff_attendance'
    __table_args__ = (
        UniqueConstraint('institution_id', 'staff_id', 'day'),
        ForeignKeyConstraint(['institution_id', 'staff_id'], ['staff_members.institution_id', 'staff_members.id']),
        CheckConstraint("status IN ('PRESENT','ABSENT','LATE','LEAVE','OFF_DUTY')"),
    )
    staff_id: Mapped[uuid.UUID] = mapped_column(index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(10))
    note: Mapped[str] = mapped_column(String(500), default='')
