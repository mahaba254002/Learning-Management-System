"""Employee records and course allocations do not require learner accounts."""
import uuid
from datetime import date
from decimal import Decimal
from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKeyConstraint, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class StaffMember(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = 'staff_members'
    __table_args__ = (
        UniqueConstraint('institution_id', 'id'), UniqueConstraint('institution_id', 'staff_number'),
        UniqueConstraint('institution_id', 'teacher_user_id'),
        ForeignKeyConstraint(['institution_id', 'department_id'], ['academic_departments.institution_id', 'academic_departments.id']),
        ForeignKeyConstraint(['institution_id', 'teacher_user_id'], ['users.institution_id', 'users.id']),
        CheckConstraint("category IN ('TEACHING','NON_TEACHING')"),
        CheckConstraint("status IN ('ACTIVE','ON_LEAVE','INACTIVE')"),
        CheckConstraint("employment_type IN ('FULL_TIME','PART_TIME','CONTRACT','VOLUNTEER')"),
        CheckConstraint("category = 'TEACHING' OR teacher_user_id IS NULL"),
    )
    staff_number: Mapped[str] = mapped_column(String(40))
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(15))
    job_title: Mapped[str] = mapped_column(String(120))
    department_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    teacher_user_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    employment_type: Mapped[str] = mapped_column(String(15), default='FULL_TIME')
    status: Mapped[str] = mapped_column(String(10), default='ACTIVE')
    joined_on: Mapped[date | None] = mapped_column(Date, nullable=True)


class StaffAllocation(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = 'staff_course_allocations'
    __table_args__ = (
        UniqueConstraint('institution_id', 'staff_id', 'course_id', 'period', 'group_name'),
        ForeignKeyConstraint(['institution_id', 'staff_id'], ['staff_members.institution_id', 'staff_members.id']),
        ForeignKeyConstraint(['institution_id', 'course_id'], ['academic_catalogue.institution_id', 'academic_catalogue.id']),
        CheckConstraint('weekly_hours > 0 AND weekly_hours <= 168'),
    )
    staff_id: Mapped[uuid.UUID] = mapped_column(index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(index=True)
    period: Mapped[str] = mapped_column(String(100))
    group_name: Mapped[str] = mapped_column(String(100), default='')
    weekly_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


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
